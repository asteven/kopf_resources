from setuptools import setup, find_packages

name = 'kopf_resources'

setup(
    name=name,
    version='0.1',
    author='Steven Armstrong',
    author_email='steven-%s@armstrong.cc' % name,
    description='sugar for handling custom resources in kopf',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'kopf',
        'pydantic',
    ],
    entry_points='''
        [console_scripts]
        {name}={name}.cli:main
    '''.format(name=name),
)

