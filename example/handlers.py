import asyncio
import logging

import kubernetes_asyncio

import kopf
import kopf_resources

from resources import Issuer, ClusterIssuer, HostCertificate


log = logging.getLogger('ssh-cert-manager')



@kopf.on.startup()
async def startup(**_):
    # Load kubernetes_asyncio config as kopf does not do that automatically for us.
    try:
        # Try incluster config first.
        kubernetes_asyncio.config.load_incluster_config()
    except kubernetes_asyncio.config.ConfigException:
        # Fall back to regular config.
        await kubernetes_asyncio.config.load_kube_config()




# We use kopf to populate a index of issuers so we don't have to call out to
# the api server to fetch the issuer for every HostCertificate that is created.
@Issuer.index(id='issuers')
@ClusterIssuer.index(id='issuers')
async def cache_issuers(namespace, name, body, **_):
    issuer = kopf_resources.from_dict(body)
    return {(namespace, name): issuer}


@HostCertificate.on.create
@HostCertificate.on.resume
@HostCertificate.on.update
async def create_host_certificate(name, namespace, body,
    issuers: kopf.Index,
    retry, **_):

    log.info('create_host_certificate: %s/%s %s', namespace, name, retry)

    certificate = kopf_resources.from_dict(body)
    print(certificate)

    assert type(certificate) == HostCertificate

    group,version = certificate.apiVersion.split('/')
    issuer_name = certificate.spec.issuerRef.name
    issuer_kind = certificate.spec.issuerRef.kind
    issuer_namespace = None
    if issuer_kind == 'Issuer':
        issuer_namespace = namespace
    print('     issuer_kind: %s' % issuer_kind)

    try:
        # Get the requested issuer from the 'issuers' index.
        issuer, *_ = issuers[(issuer_namespace, issuer_name)]
    except KeyError as e:
        if retry < 5:
            raise kopf.TemporaryError('Issuer not found in cache.', delay=10) from e
        else:
            raise kopf.PermanentError(f'Issuer not found in cache after {retry} tries. Giving up.')

    print(f'certificate: {certificate}')
    print(f'issuer: {issuer}')

    # Now do something interesting with cert and issuer.



@HostCertificate.on.delete
async def delete_host_certificate(name, namespace, body, **_):
    log.info('delete_host_certificate: %s/%s', namespace, name)
    certificate = kopf_resources.from_dict(body)
    print(certificate)
    assert type(certificate) == HostCertificate

