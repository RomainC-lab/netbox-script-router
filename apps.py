from netbox.plugins import PluginConfig


class ScriptRouterConfig(PluginConfig):
    name = 'netbox_script_router'
    verbose_name = 'Script Router'
    description = 'Route NetBox scripts to dedicated RQ workers via Meta.queue'
    version = '1.0.0'
    author = 'Romain'
    base_url = 'script-router'

    def ready(self):
        super().ready()
        from .patch import apply_patch
        apply_patch()
