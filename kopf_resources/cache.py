import functools
import logging

from pydantic.typing import Dict

import kopf

from .resources import Resource


log = logging.getLogger('kopf_resources')



class ResourceNotFound(Exception):
    pass



class ResourceCache():
    """Automagic resource cache.
    If resources are created or updated they are added to the cache.
    If resources are deleted they are removed from the cache.

    mycache = ResourceCache(MyResource)
    instance = mycache.get(resource_name, namespace=namespace)
    """

    __kopf_decorators__ = {
        'add': (
            'create',
            'update',
            'resume',
        ),
        'remove': (
            'delete',
        )
    }


    def __init__(self, resource_definition: Resource):
        self.resource_definition = resource_definition
        self.__cache = {}

        crd = self.resource_definition
        args = (crd.__group__, crd.__version__, crd.__plural__)
        for operation_name, decorator_names in self.__kopf_decorators__.items():
            def bind_handler(operation_handler, decorator_names):
                for name in decorator_names:
                    kopf_decorator = getattr(kopf.on, name)
                    handler = kopf_decorator(*args)

                    @functools.wraps(operation_handler)
                    def wrapper(*args, **kwargs):
                        return operation_handler(*args, **kwargs)

                    handler(wrapper)

            operation_handler = getattr(self, operation_name)
            bind_handler(operation_handler, decorator_names)


    def add(self, body, **_):
        resource = self.resource_definition.parse_obj(body)
        namespace = resource.metadata.namespace
        name = resource.metadata.name
        if namespace:
            key = f'{namespace}/{name}'
        else:
            key = name
        log.debug('ResourceCache.add: %s', key)
        self.__cache[key] = resource


    def remove(self, name, namespace, **_):
        if namespace:
            key = f'{namespace}/{name}'
        else:
            key = name
        log.debug('ResourceCache.remove: %s', key)
        try:
            del self.__cache[key]
        except KeyError as e:
            # ignored
            pass


    def get(self, name, namespace=None):
        if namespace:
            key = f'{namespace}/{name}'
        else:
            key = name
        log.debug('ResourceCache.get: %s', key)
        try:
            return self.__cache[key]
        except KeyError as e:
            raise ResourceNotFound(f'Resource not found in cache: {self.resource_definition}, {key}')

