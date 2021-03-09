import asyncio
import logging

import kubernetes_asyncio

import kopf

from kopf_resources import ResourceCache, ResourceNotFound

from resources import Issuer, ClusterIssuer, HostCertificate, HostCertificateSpec


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



# We use kopf to populate a cache of issuers so we don't have to call out to
# the api server to fetch the issuer for every HostCertificate that is created.
issuer_cache = {
    'Issuer': ResourceCache(Issuer),
    'ClusterIssuer': ResourceCache(ClusterIssuer),
}

def get_issuer_from_cache(issuer_kind, issuer_name, issuer_namespace):
    cache = issuer_cache[issuer_kind]
    return cache.get(issuer_name, namespace=issuer_namespace)


@HostCertificate.on.create
@HostCertificate.on.resume
@HostCertificate.on.update
async def create_host_certificate(name, namespace,
    body: HostCertificate,
    meta,
    spec: HostCertificateSpec,
    retry,
    patch, logger, **_):

    log.info('create_host_certificate: %s/%s %s', namespace, name, retry)

    assert type(body) == HostCertificate

    group,version = body.apiVersion.split('/')
    issuer_name = spec.issuerRef.name
    issuer_kind = spec.issuerRef.kind
    issuer_namespace = None
    if issuer_kind == 'Issuer':
        issuer_namespace = namespace

    try:
        issuer = get_issuer_from_cache(issuer_kind, issuer_name, issuer_namespace)
    except ResourceNotFound as e:
        if retry < 5:
            raise kopf.TemporaryError('Issuer not found in cache.', delay=10) from e
        else:
            raise kopf.PermanentError(f'Issuer not found in cache after {retry} tries. Giving up.')

    print(f'hostcertificate: {body}')
    print(f'issuer: {issuer}')

    # Now do something interesting with cert and issuer.



@HostCertificate.on.delete
async def delete_host_certificate(name, namespace, body: HostCertificate, **_):
    log.info('delete_host_certificate: %s/%s', namespace, name)

