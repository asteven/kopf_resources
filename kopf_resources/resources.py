import functools
import inspect
import types
import typing

import kopf

from pydantic import BaseModel, Field
from pydantic.typing import Any, Dict, Literal, List, Mapping, Type


def dereference_schema(schema, definitions, parent=None, key=None):
    """Find and dereference objects in the given schema.

    '#/definitions/myElement' -> schema[definitions][myElement]
    """
    if hasattr(schema, 'items'):
        for k, v in schema.items():
            if k == '$ref':
                #print('%s -> %s' % (key, v))
                ref_name = v.rpartition('/')[-1]
                definition = definitions[ref_name]
                if isinstance(parent, dict):
                    parent[key] = definition
                elif isinstance(parent, list):
                    parent[parent.index(key)] = definition
                v = definition
            if isinstance(v, dict):
                dereference_schema(v, definitions, parent=schema, key=k)
            elif isinstance(v, list):
                for i,d in enumerate(v):
                    dereference_schema(d, definitions, parent=v, key=d)
            #else:
            #    print('unhandled k: %s; v: %s; %s' % (k, v, type(v)))



class DecoratorWrapper():
    """A class that wrapps a kopf resource handling decorator.

    It injects the resource specific parameters so users don't have to.

    It can be used as a descriptor on a class as done with the DecoratorProxy
    class below.

    Alternatively it can be used explicitly by passing the kopf decorator name
    and the required resource parameters to the constructor. An example of this
    usage is available in the ResourceCache class which is part of this package.

    e.g.
    ```
        def func(*args):
            pass

        decorator = DecoratorWrapper('create', ('example.com', 'v1', 'myresources')
        func = decorator(func)
    ```
    """

    def __init__(self, name=None, args=None):
        # This method is only used in explicit/manual mode.
        self.name = name
        self.args = args


    def __call__(self, func):
        # This method is only used in explicit/manual mode.
        return self.decorator(func)


    def __set_name__(self, owner, name):
        # This method is only used in descriptor mode.

        # Store the name of this decorator wrapper so we can call the
        # apropriate kopf decorator later on.
        self.name = name


    def __get__(self, instance, owner):
        # This method is only used in descriptor mode.
        print(f'DecoratorWrapper.__get__: {instance}, {owner}')
        resource = instance.owner
        self.args = (resource.__group__, resource.__version__, resource.__plural__)
        return self.decorator


    def decorator(self, *args, **kwargs):
        """Decorator function that uses the name and resource specific
        parameters available to this class to wrap the corresponding
        kopf.on.$name decorator.
        """
        #print(f'DecoratorWrapper.decorator: {self.name}: {args}, {kwargs}')
        if len(args) == 1 and callable(args[0]):
            # Used as:
            # @SomeResource.on.create
            # def some_function(*args, **kwargs):
            #     pass
            func = args[0]
            d_args = kwargs.get('__args', self.args)
            d_kwargs = kwargs.get('__kwargs', {})
        else:
            # Used as:
            # @SomeResource.on.create(when=some_filter, labels=...)
            # def some_function(*args, **kwargs):
            #     pass

            # Inject our resource specific args to comply with kopf's decorator
            # signatures.
            all_args = self.args + args
            return functools.partial(self.decorator, __args=all_args, __kwargs=kwargs)


        #print(f'name: {self.name}')
        #print(f'     func: {func}')
        #print(f'     d_args: {d_args}')
        #print(f'     d_kwargs: {d_kwargs}')
        kopf_decorator = getattr(kopf.on, self.name)
        handler = kopf_decorator(*d_args, **d_kwargs)
        signature = inspect.signature(func)
        type_hints = typing.get_type_hints(func)
        #print('     signature: %s' % signature)
        #print('     type_hints: %s' % type_hints)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Wrapper function that parses pydantic models based on
            # typing hints.
            #print('     wrapper: %s; %s' % (args, kwargs))
            for argument_name, argument_type in type_hints.items():
                # NOTE: BaseModel is pydantic specific. Will need a way to
                #       make this configurable if other datamodel packages
                #       should be supported.
                if issubclass(argument_type, BaseModel):
                    _object = kwargs[argument_name]
                    kwargs[argument_name] = argument_type.parse_obj(_object)

            return func(*args, **kwargs)
        return handler(wrapper)





class DecoratorProxy():
    """Descriptor class that dispatches decorators to kopf.on.$name.
    """

    def __get__(self, instance, owner):
        # Store a reference to the Resource subclass we are used on.
        # This is used in the DecoratorWrapper instances to access
        # the __kind__, __group__ and __plural__ members of the resource.
        self.owner = owner
        return self

    resume = DecoratorWrapper()
    create = DecoratorWrapper()
    update = DecoratorWrapper()
    delete = DecoratorWrapper()
    field = DecoratorWrapper()
    event = DecoratorWrapper()
    daemon = DecoratorWrapper()
    timer = DecoratorWrapper()



class DecoratorMixin():
    """Sugar to let the decorator proxy be used as a mixin base class.
    """

    on = DecoratorProxy()



class ObjectMeta(BaseModel):
    """Resource ObjectMeta
    """
    # https://kubernetes.github.io/cluster-registry/reference/build/index.html#objectmeta-v1
    name: str
    namespace: str = None
    labels: Dict[str,str] = Field(default_factory=dict)
    annotations: Dict[str,str] = Field(default_factory=dict)
    uuid: str = None

    # TODO: add more of these ...
    #creationTimestamp
    #deletionGracePeriodSeconds
    finalizers: List[str] = Field(default_factory=list)



class Spec(BaseModel):
    pass



class Status(BaseModel):
    pass



class Resource(BaseModel, DecoratorMixin):
    __spec__ = None
    __group__ = None
    __version__ = None
    __kwargs__ = None
    __status_subresource__ = False

    # This would also work instead of inheriting from the DecoratorMixin
    # base class.
    #on = DecoratorProxy()

    def __init_subclass__(cls, /, group, version, scope='Namespaced',
            status_subresource=False, **kwargs):
        name = cls.__name__
        cls.__group__ = group
        cls.__version__ = version
        cls.__status_subresource__ = status_subresource
        cls.__plural__ = plural = kwargs.get('plural', f'{name.lower()}s')
        cls.__fqname__ = f'{cls.__plural__}.{cls.__group__}'
        cls.__spec__ = {
            'group': group,
            'names': {
                'kind': name,
                'listKind': f'{name}List',
                'singular': kwargs.get('singular', name.lower()),
                'plural': plural
            },
            'scope': scope,
        }

    apiVersion: str
    kind: str
    metadata: ObjectMeta = None

    @classmethod
    def as_crd(cls):
        """Create and return a CustomResourceDefinition for this resource.
        """
        name = cls.__name__
        spec = cls.__spec__.copy()
        group = spec['group']
        plural_name = spec['names']['plural']
        body = {
            'apiVersion': 'apiextensions.k8s.io/v1',
            'kind': 'CustomResourceDefinition',
            'metadata': {'name': cls.__fqname__},
            'spec': spec,
        }

        schema = cls.schema()
        if 'definitions' in schema:
            definitions = schema.pop('definitions')
            dereference_schema(schema, definitions)

        # Don't want ObjectMeta in crd.
        del schema['properties']['metadata']

        # TODO: support different versions?
        version = {
            'name': cls.__version__,
            'schema': {'openAPIV3Schema': schema},
            'served': True,
            'storage': True,
        }
        if cls.__status_subresource__:
            version.setdefault('subresources', {})
            version['subresources']['status'] = {}
        body['spec']['versions'] = [version]
        return body


    def __str__(self):
        _str = super().__str__()
        return f'<Resource {_str}>'
