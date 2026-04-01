# netbox-script-router

Plugin NetBox 3.7.8 — Route les scripts vers des workers RQ dédiés via `Meta.queue`.

## Installation

```bash
pip install ./netbox-script-router
```

Dans `configuration.py` :

```python
PLUGINS = ['netbox_script_router']

PLUGINS_CONFIG = {
    'netbox_script_router': {
        'queues': ['myworker'],
    },
}
```

## Utilisation

Ajouter `queue` dans la classe `Meta` des scripts à router :

```python
from extras.scripts import Script

class MonScript(Script):
    class Meta:
        name = "Script"
        queue = "myworker"

    def run(self, data, commit):
        self.log_success("Je tourne sur le worker myworker !")
```

Les scripts sans `Meta.queue` restent sur le worker `default`.

## Lancer les workers

```bash
# Worker dédié myworker
python manage.py rqworker myworker

# Worker pour le reste
python manage.py rqworker default high low
```
