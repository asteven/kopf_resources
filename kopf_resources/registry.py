
class ResourceNotFoundError(Exception):
    pass



class ResourceRegistry():
    __versions = {}
    __resources = {}


    @classmethod
    def add(cls, resource_class):
        # To get all versions of a resource.
        cls.__versions.setdefault(resource_class.__fqname__, {})
        cls.__versions[resource_class.__fqname__][resource_class.__version__] = resource_class
        # For easy access via (apiVersion, kind) tuple.
        key = (resource_class.__api_version__, resource_class.__kind__)
        cls.__resources[key] = resource_class


    @classmethod
    def get(cls, api_version, kind):
        key = (api_version, kind)
        try:
            return cls.__resources[key]
        except KeyError as e:
            msg = f'Could not find resource class for: {key}'
            raise ResourceNotFoundError() from e


    @classmethod
    def get_version(cls, fqname, version):
        try:
            return cls.__versions[fqname][version]
        except KeyError as e:
            msg = f'Could not find resource class for: {fqname}, {version}'
            raise ResourceNotFoundError() from e


    @classmethod
    def iter_versions(cls, resource_class):
        try:
            return iter(cls.__versions[resource_class.__fqname__].items())
        except KeyError as e:
            msg = f'Could not find resource classes for: {fqname}'
            raise ResourceNotFoundError() from e


    @classmethod
    def iter_resources(cls):
        return iter(cls.__resources.values())
