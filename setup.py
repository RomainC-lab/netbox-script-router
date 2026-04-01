from setuptools import setup

setup(
    name='netbox-script-router',
    version='1.1.0',
    description='Route NetBox scripts to dedicated RQ workers via Meta.queue',
    packages=['netbox_script_router'],
    package_dir={'netbox_script_router': '.'},
    install_requires=[],
)
