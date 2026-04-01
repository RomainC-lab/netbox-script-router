"""
Tests unitaires pour netbox_script_router.patch
"""

import sys
from unittest.mock import MagicMock, patch as mock_patch

from django.conf import settings
from core.models import Job
import utilities.rqworker as rqworker_mod

# Add parent dir to path so we can import patch directly
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
import patch as script_router_patch


# -- Helpers -----------------------------------------------------------------

def _reset_patch_state():
    """Reset global state so each test starts clean."""
    script_router_patch._original_enqueue = None
    script_router_patch._original_get_queue = None
    Job.enqueue = classmethod(lambda cls, func, instance, **kw: 'default_result')
    rqworker_mod.get_queue_for_model = lambda model: 'default'
    settings.PLUGINS_CONFIG = {}
    settings.RQ_QUEUES = {'default': {'HOST': 'localhost', 'PORT': 6379}}


def _make_script_class(queue_name=None):
    """Create a fake script class with optional Meta.queue."""
    attrs = {}
    if queue_name is not None:
        attrs['Meta'] = type('Meta', (), {'queue': queue_name})
    return type('FakeScript', (), attrs)


# -- Tests: double-patch guard -----------------------------------------------

class TestDoubleApplyPatch:
    def setup_method(self):
        _reset_patch_state()

    def test_apply_patch_sets_originals(self):
        script_router_patch.apply_patch()
        assert script_router_patch._original_enqueue is not None
        assert script_router_patch._original_get_queue is not None

    def test_double_apply_does_not_overwrite(self):
        script_router_patch.apply_patch()
        first_original = script_router_patch._original_enqueue

        script_router_patch.apply_patch()
        assert script_router_patch._original_enqueue is first_original

    def test_enqueue_is_replaced_after_patch(self):
        original = Job.enqueue
        script_router_patch.apply_patch()
        assert Job.enqueue is not original


# -- Tests: _resolve_queue ---------------------------------------------------

class TestResolveQueue:
    def setup_method(self):
        _reset_patch_state()

    def test_returns_queue_from_meta(self):
        cls = _make_script_class('my_worker')
        with mock_patch.object(script_router_patch, '_get_script_class', return_value=cls):
            assert script_router_patch._resolve_queue(MagicMock(), 'test') == 'my_worker'

    def test_returns_none_without_meta_queue(self):
        cls = _make_script_class(queue_name=None)
        with mock_patch.object(script_router_patch, '_get_script_class', return_value=cls):
            assert script_router_patch._resolve_queue(MagicMock(), 'test') is None

    def test_returns_none_when_class_not_found(self):
        with mock_patch.object(script_router_patch, '_get_script_class', return_value=None):
            assert script_router_patch._resolve_queue(MagicMock(), 'test') is None

    def test_returns_none_on_exception(self):
        with mock_patch.object(script_router_patch, '_get_script_class', side_effect=RuntimeError('boom')):
            assert script_router_patch._resolve_queue(MagicMock(), 'test') is None


# -- Tests: patched enqueue --------------------------------------------------

class TestPatchedEnqueue:
    def setup_method(self):
        _reset_patch_state()
        script_router_patch.apply_patch()

    def test_routes_to_custom_queue(self):
        cls = _make_script_class('custom_q')
        with mock_patch.object(script_router_patch, '_get_script_class', return_value=cls):
            Job.enqueue(lambda: None, MagicMock(), name='s')
        # After the call, context var must be reset
        assert script_router_patch._queue_override.get() is None

    def test_context_var_reset_on_exception(self):
        cls = _make_script_class('custom_q')

        # Replace the saved original with one that explodes
        real_original = script_router_patch._original_enqueue

        @classmethod
        def exploding(klass, func, instance, name='', user=None,
                      schedule_at=None, interval=None, **kw):
            raise ValueError('boom')

        # Attach to a temporary class so __func__ works
        type('_Tmp', (), {'enqueue': exploding})
        script_router_patch._original_enqueue = exploding

        with mock_patch.object(script_router_patch, '_get_script_class', return_value=cls):
            try:
                Job.enqueue(lambda: None, MagicMock(), name='s')
            except ValueError:
                pass

        assert script_router_patch._queue_override.get() is None
        script_router_patch._original_enqueue = real_original

    def test_no_override_without_meta_queue(self):
        cls = _make_script_class(queue_name=None)
        with mock_patch.object(script_router_patch, '_get_script_class', return_value=cls):
            Job.enqueue(lambda: None, MagicMock(), name='s')
        assert script_router_patch._queue_override.get() is None


# -- Tests: patched get_queue_for_model --------------------------------------

class TestPatchedGetQueue:
    def setup_method(self):
        _reset_patch_state()
        script_router_patch.apply_patch()

    def test_returns_override_when_set(self):
        token = script_router_patch._queue_override.set('special')
        try:
            result = script_router_patch._patched_get_queue_for_model(MagicMock())
            assert result == 'special'
        finally:
            script_router_patch._queue_override.reset(token)

    def test_falls_back_to_original_when_no_override(self):
        result = script_router_patch._patched_get_queue_for_model(MagicMock())
        assert result == 'default'


# -- Tests: _register_custom_queues -----------------------------------------

class TestRegisterCustomQueues:
    def setup_method(self):
        _reset_patch_state()

    def test_registers_new_queues(self):
        settings.PLUGINS_CONFIG = {
            'netbox_script_router': {'queues': ['worker_a', 'worker_b']},
        }
        script_router_patch._register_custom_queues()

        assert 'worker_a' in settings.RQ_QUEUES
        assert 'worker_b' in settings.RQ_QUEUES
        assert settings.RQ_QUEUES['worker_a']['HOST'] == 'localhost'

    def test_does_not_overwrite_existing_queue(self):
        settings.RQ_QUEUES['existing'] = {'HOST': 'custom'}
        settings.PLUGINS_CONFIG = {
            'netbox_script_router': {'queues': ['existing']},
        }
        script_router_patch._register_custom_queues()

        assert settings.RQ_QUEUES['existing']['HOST'] == 'custom'

    def test_noop_when_no_queues_configured(self):
        settings.PLUGINS_CONFIG = {}
        rq_before = dict(settings.RQ_QUEUES)
        script_router_patch._register_custom_queues()
        assert settings.RQ_QUEUES == rq_before
