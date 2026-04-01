"""
Setup fake modules to satisfy imports inside patch.py without NetBox installed.
"""

import sys
import types
from unittest.mock import MagicMock

# -- Fake modules ------------------------------------------------------------

# django.conf.settings
django_mod = types.ModuleType('django')
django_conf = types.ModuleType('django.conf')
django_conf.settings = MagicMock()
django_conf.settings.PLUGINS_CONFIG = {}
django_conf.settings.RQ_QUEUES = {}
django_mod.conf = django_conf
sys.modules.setdefault('django', django_mod)
sys.modules.setdefault('django.conf', django_conf)

# core.models.Job
core = types.ModuleType('core')
core_models = types.ModuleType('core.models')
_job_cls = type('Job', (), {})
_job_cls.enqueue = classmethod(lambda cls, func, instance, **kw: 'default_result')
core_models.Job = _job_cls
core.models = core_models
sys.modules.setdefault('core', core)
sys.modules.setdefault('core.models', core_models)

# utilities.rqworker
utilities = types.ModuleType('utilities')
utilities_rqworker = types.ModuleType('utilities.rqworker')
utilities_rqworker.get_queue_for_model = lambda model: 'default'
utilities.rqworker = utilities_rqworker
sys.modules.setdefault('utilities', utilities)
sys.modules.setdefault('utilities.rqworker', utilities_rqworker)

# extras.models
extras = types.ModuleType('extras')
extras_models = types.ModuleType('extras.models')
extras.models = extras_models
sys.modules.setdefault('extras', extras)
sys.modules.setdefault('extras.models', extras_models)

# netbox.plugins (for apps.py)
netbox_mod = types.ModuleType('netbox')
netbox_plugins = types.ModuleType('netbox.plugins')
netbox_plugins.PluginConfig = type('PluginConfig', (), {})
netbox_mod.plugins = netbox_plugins
sys.modules.setdefault('netbox', netbox_mod)
sys.modules.setdefault('netbox.plugins', netbox_plugins)
