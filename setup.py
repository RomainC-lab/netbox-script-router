from setuptools import setup, find_packages

setup(
    name='netbox-script-router',
    version='1.0.0',
    description='Route NetBox scripts to dedicated RQ workers via Meta.queue',
    packages=find_packages(),
    install_requires=[
        'django-rq',
    ],
)
