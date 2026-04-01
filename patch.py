"""
Monkey-patch de Job.enqueue pour router les scripts NetBox
vers des workers RQ dédiés via l'attribut Meta.queue.

Compatible NetBox 3.7.x et 4.0+.
Thread-safe grâce à contextvars.
"""

import contextvars
import logging

from core.models import Job
import utilities.rqworker as rqworker

logger = logging.getLogger('netbox_script_router')

_queue_override = contextvars.ContextVar('script_router_queue', default=None)
_original_enqueue = None
_original_get_queue = None


@classmethod
def _patched_enqueue(cls, func, instance, name='', user=None, schedule_at=None, interval=None, **kwargs):
    queue_name = _resolve_queue(instance, name)

    if queue_name:
        token = _queue_override.set(queue_name)
        try:
            return _original_enqueue.__func__(
                cls, func, instance, name=name, user=user,
                schedule_at=schedule_at, interval=interval, **kwargs,
            )
        finally:
            _queue_override.reset(token)

    return _original_enqueue.__func__(
        cls, func, instance, name=name, user=user,
        schedule_at=schedule_at, interval=interval, **kwargs,
    )


def _patched_get_queue_for_model(model):
    override = _queue_override.get()
    if override:
        return override
    return _original_get_queue(model)


def _resolve_queue(instance, script_name):
    """
    Extrait Meta.queue depuis la classe de script associée à l'instance.
    Gère ScriptModule (NetBox 3.7.x) et Script model (NetBox 4.0+).
    """
    try:
        script_cls = _get_script_class(instance, script_name)
        if script_cls is None:
            return None

        queue = getattr(getattr(script_cls, 'Meta', None), 'queue', None)
        if queue:
            logger.info("Script '%s' routed to queue '%s'", script_name, queue)
            return queue

    except Exception as e:
        logger.warning("Script router: error resolving queue for '%s': %s", script_name, e)

    return None


def _get_script_class(instance, script_name):
    # NetBox 4.0+ : extras.models.Script (modèle DB avec python_class())
    try:
        from extras.models import Script as ScriptModel
        if hasattr(ScriptModel, 'python_class') and isinstance(instance, ScriptModel):
            return instance.python_class
    except ImportError:
        pass

    # NetBox 3.7.x : extras.models.ScriptModule
    try:
        from extras.models import ScriptModule
        if not isinstance(instance, ScriptModule):
            return None

        scripts = instance.scripts
        script_cls = scripts.get(script_name)

        # Fallback : "module.ClassName" -> "ClassName"
        if script_cls is None and script_name:
            suffix = script_name.rsplit('.', 1)[-1]
            script_cls = scripts.get(suffix)

        return script_cls
    except ImportError:
        return None


def _register_custom_queues():
    from django.conf import settings

    custom_queues = settings.PLUGINS_CONFIG.get('netbox_script_router', {}).get('queues', [])
    if not custom_queues:
        return

    rq_queues = getattr(settings, 'RQ_QUEUES', {})
    default_params = rq_queues.get('default', {})

    for queue_name in custom_queues:
        if queue_name not in rq_queues:
            rq_queues[queue_name] = default_params.copy()
            logger.info("Registered RQ queue '%s'", queue_name)


def apply_patch():
    global _original_enqueue, _original_get_queue

    if _original_enqueue is not None:
        logger.debug("Script router patch already applied, skipping")
        return

    _register_custom_queues()

    _original_enqueue = Job.enqueue
    _original_get_queue = rqworker.get_queue_for_model

    rqworker.get_queue_for_model = _patched_get_queue_for_model
    Job.enqueue = _patched_enqueue
    logger.info("Job.enqueue patched for script routing")
