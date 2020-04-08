This lambda function will periodically poll EKS Cluster for any new NODEPORT Service and will expose it to NLB. This will enable UDP routing which is currently not supported on EKS via NLB.

https://github.com/kubernetes/kubernetes/issues/79523
