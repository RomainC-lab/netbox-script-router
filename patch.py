"""
Monkey-patch de Job.enqueue pour router les scripts NetBox
vers des workers RQ dédiés via l'attribut Meta.queue.
"""

import logging

import django_rq
from django.conf import settings

from core.models import Job
from utilities.rqworker import get_queue_for_model

logger = logging.getLogger('netbox_script_router')

# Sauvegarde de l'original
_original_enqueue = Job.enqueue


@classmethod
def _patched_enqueue(cls, func, instance, name='', user=None, schedule_at=None, interval=None, **kwargs):
    """
    Wrapper autour de Job.enqueue qui redirige les scripts
    ayant Meta.queue vers le worker RQ correspondant.
    """
    queue_override = _get_script_queue(instance, name)

    if queue_override:
        # Patch temporaire de get_queue_for_model pour forcer la queue
        import utilities.rqworker as rqworker
        original_get_queue = rqworker.get_queue_for_model

        rqworker.get_queue_for_model = lambda *a, **kw: queue_override
        try:
            return _original_enqueue.__func__(cls, func, instance, name=name, user=user,
                                              schedule_at=schedule_at, interval=interval, **kwargs)
        finally:
            rqworker.get_queue_for_model = original_get_queue
    else:
        return _original_enqueue.__func__(cls, func, instance, name=name, user=user,
                                          schedule_at=schedule_at, interval=interval, **kwargs)


def _get_script_queue(instance, script_name):
    """
    Si instance est un ScriptModule et que le script a Meta.queue, retourne le nom de la queue.
    Sinon retourne None (= comportement par défaut).
    """
    try:
        from extras.scripts import Script
        from extras.models import ScriptModule

        if not isinstance(instance, ScriptModule):
            return None

        scripts = instance.scripts

        # Tentative directe avec le nom fourni
        script_cls = scripts.get(script_name)

        # Fallback : chercher par suffixe (le name peut être "module.ClassName" ou "ClassName")
        if script_cls is None and script_name:
            for key, cls in scripts.items():
                if key == script_name.split('.')[-1] or script_name.endswith(key):
                    script_cls = cls
                    break

        if script_cls is None:
            return None

        queue = getattr(getattr(script_cls, 'Meta', None), 'queue', None)
        if queue:
            logger.info(f"Script '{script_name}' routed to queue '{queue}'")
            return queue

    except Exception as e:
        logger.warning(f"Script router: error resolving queue for '{script_name}': {e}")

    return None


def _register_custom_queues():
    """
    Enregistre les queues custom dans RQ_QUEUES de Django
    en réutilisant les paramètres de connexion de la queue 'default'.
    """
    custom_queues = getattr(settings, 'PLUGINS_CONFIG', {}).get('netbox_script_router', {}).get('queues', [])

    if not custom_queues:
        return

    rq_queues = getattr(settings, 'RQ_QUEUES', {})
    # Copier les params de connexion depuis la queue 'default'
    default_params = rq_queues.get('default', {})

    for queue_name in custom_queues:
        if queue_name not in rq_queues:
            rq_queues[queue_name] = default_params.copy()
            logger.info(f"Registered RQ queue '{queue_name}'")


def apply_patch():
    _register_custom_queues()
    Job.enqueue = _patched_enqueue
    logger.info("Job.enqueue patched for script routing")
