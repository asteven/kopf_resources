from .registry import (
    ResourceRegistry,
    ResourceNotFoundError,
)

from .resources import (
    Resource,
    Spec,
    Status,
)

from .cache import (
    ResourceCache,
    ResourceNotFound,
)



def from_dict(body):
    """Parse the given body dict into a resource instance.
    """
    resource_class = ResourceRegistry.get(body['apiVersion'], body['kind'])
    return resource_class.parse_obj(body)



def as_crd(resource_class):
    """Create and return a CustomResourceDefinition for the given resource class.
    """
    spec = resource_class.__spec__.copy()
    group = spec['group']
    plural_name = spec['names']['plural']
    body = {
        'apiVersion': 'apiextensions.k8s.io/v1',
        'kind': 'CustomResourceDefinition',
        'metadata': {'name': resource_class.__fqname__},
        'spec': spec,
    }

    for version, resource_class in ResourceRegistry.iter_versions(resource_class):
        schema = resource_class.schema()
        if 'definitions' in schema:
            definitions = schema.pop('definitions')
            _dereference_schema(schema, definitions)

        _version = {
            'name': version,
            'schema': {'openAPIV3Schema': schema},
            'served': resource_class.__served__,
            'storage': resource_class.__storage__,
        }

        if resource_class.__status_subresource__:
            _version.setdefault('subresources', {})
            _version['subresources']['status'] = {}

        body['spec']['versions'].append(_version)

    return body



def all_crds(include_private=False):
    """Create and return CustomResourceDefinition's for all known and loaded resource classes.
    """
    crds = {}
    for resource_class in ResourceRegistry.iter_resources():
        print(f'resource_class: {resource_class}')
        if include_private or not resource_class.__name__.startswith('_'):
            if not resource_class.__fqname__ in crds:
                crds[resource_class.__fqname__] = as_crd(resource_class)
    return crds.values()



def _dereference_schema(schema, definitions, parent=None, key=None):
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
                _dereference_schema(v, definitions, parent=schema, key=k)
            elif isinstance(v, list):
                for i,d in enumerate(v):
                    _dereference_schema(d, definitions, parent=v, key=d)
            #else:
            #    print('unhandled k: %s; v: %s; %s' % (k, v, type(v)))

