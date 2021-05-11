import yaml


from .registry import (
    ResourceRegistry,
    ResourceNotFoundError,
)

from .resources import (
    Resource,
    Spec,
    Status,
)



def from_dict(body):
    """Parse the given body dict into a resource instance.
    """
    resource_class = ResourceRegistry.get(body['apiVersion'], body['kind'])
    return resource_class.parse_obj(body)



class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True



def to_yaml(*crds):
    """Helper function to serialize one or more CRD's to a yaml document
    that kubernetes understands.

    We mainly have to prevent the yaml Dumper from using any alias references
    as kubernetes does not understand those.
    """
    return yaml.dump_all(crds, sort_keys=False, Dumper=NoAliasDumper)



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
            # First dereference any nested definitions.
            # This is just a performance optimisation so we only dereference
            # each models once instead of repeating that for each reference.
            _dereference_schema(definitions, definitions)
            # Then dereference the actual schema.
            _dereference_schema(schema, definitions)
            # Then cleanup the schema into something that kubernetes agrees with.
            _clean_schema(schema)

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
        #print(f'resource_class: {resource_class}')
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
                #print(f'{type(parent)} {key}: {k} -> {v}')
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
            #    print(f'unhandled k: {k}; v: {v}; %s' % type(v))



def _clean_schema(schema):
    """Clean the schema for use with kubernetes.

    Pydantic uses allOf to preserve some fields like title and description
    that would otherwise be overwritten by nested models.
    Kubernetes does not like that so we work around that by merging
    the nested models properties.

    We basically turn this:

    ```
    {
       'tokenSecretRef': {
          'title': 'Tokensecretref',
          'description': 'Some interesting field description.',
          'allOf': [{
             'title': 'SecretRef',
             'description': 'Some model docstring.',
             'type': 'object',
             'properties': {
                'name': {'title': 'Name', 'type': 'string'}, 'key': {'title': 'Key', 'type': 'string'}
             },
             'required': ['name']
          }]
       }
    }
    ```

    into this:

    ```
    {
       'tokenSecretRef': {
          'title': 'Tokensecretref',
          'description': 'Some interesting field description.',
          'type': 'object',
          'properties': {
             'name': {'title': 'Name', 'type': 'string'}, 'key': {'title': 'Key', 'type': 'string'}
          },
          required': ['name']
       }
    }
    ```
    """
    if hasattr(schema, 'items'):
        if 'allOf' in schema:
            value = schema['allOf']
            if len(value) == 1:
                child = value[0]
                for k,v in child.items():
                    schema.setdefault(k, v)
                schema.pop('allOf')
        else:
            if isinstance(schema, dict):
                for k,v in schema.items():
                    _clean_schema(v)
            elif isinstance(schema, list):
                for i,d in enumerate(schema):
                    _clean_schema(d)
