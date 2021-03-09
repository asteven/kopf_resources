# kopf_resources example

This is just an example ripped out of a project to give an idea of
how this all fits together.


## Generate CRDS from Resources

```
python ./resources.py
```

## Add CRDS to kubernetes cluster

Obviously read/understand before doing.

```
python ./resources.py | kubectl apply -f -
```

## Run the handlers

```
kopf run ./handlers.py
```


## Create/delete resources

```
kubectl apply -f ./issuer.yaml
kubectl apply -f ./hostcertificate.yaml
```

```
kubectl delete -f ./hostcertificate.yaml
kubectl delete -f ./issuer.yaml
```
