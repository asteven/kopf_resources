import yaml

from pydantic import BaseModel, Field
from pydantic.typing import Any, Dict, Literal, List, Mapping, Type


import kopf_resources
from kopf_resources import Resource, Spec, Status



class IssuerSpec(Spec):

    path: str = Field(description='The mount path of the Vault SSH backend.')
    server: str = Field(description='The connection address for the Vault server, e.g: "https://vault.example.com:8200".')
    role: str = Field(description='The vault role to use to issue certificates.')



class Issuer(Resource, group='ssh-cert-manager.io', version='v1', scope='Namespaced'):
    """A Issuer represents a vault ssh certificate authority which can be
    referenced as part of `issuerRef` fields. It is scoped to a single
    namespace and can therefore only be referenced by resources within the
    same namespace."""
    spec: IssuerSpec


class ClusterIssuer(Resource, group='ssh-cert-manager.io', version='v1', scope='Cluster'):
    """A ClusterIssuer represents a vault ssh certificate authority which can
    be referenced as part of `issuerRef` fields. It is similar to an Issuer,
    however it is cluster-scoped and therefore can be referenced by resources
    that exist in *any* namespace, not just the same namespace as the referent."""
    spec: IssuerSpec



class IssuerRef(BaseModel):
    name: str
    kind: str



class HostCertificateSpec(Spec):
    secretName: str
    issuerRef: IssuerRef
    principals: List[str] = Field(default_factory=list, description='List of principals to add to the certificate. Defaults to the name of the HostCertificate.')
    keyTypes: List[str] = Field(default_factory=list)
    extensions: Dict[str,str] = Field(default_factory=dict)
    criticalOptions: Dict[str,str] = Field(default_factory=dict)



class HostCertificate(Resource, group='ssh-cert-manager.io', version='v1', scope='Namespaced'):
    spec: HostCertificateSpec



# Demonstrate support for multiple versions
class HostCertificateSpecV1alpha2(Spec):
    secretName: str
    issuerRef: IssuerRef
    principals: List[str] = Field(default_factory=list, description='List of principals to add to the certificate. Defaults to the name of the HostCertificate.')
    keyTypes: List[str] = Field(default_factory=list)

    # extensions and criticalOptions did not exist in v1alpha2 version
    #extensions: Dict[str,str] = Field(default_factory=dict)
    #criticalOptions: Dict[str,str] = Field(default_factory=dict)


class HostCertificateV1alpha2(Resource, kind='HostCertificate', group='ssh-cert-manager.io', version='v1alpha2', scope='Namespaced', storage=False):
    spec: HostCertificateSpecV1alpha2



def print_crds():
    crds = kopf_resources.all_crds()
    print(yaml.dump_all(crds, sort_keys=False))



if __name__ == '__main__':
    print_crds()

