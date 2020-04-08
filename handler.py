import boto3
import os
import kubernetes
import urllib3

def get_nodes(api_instance):
    instanceIDs = {}
    api_response = api_instance.list_node()
    for i in api_response.items:
        instanceIDs[i.spec.provider_id.split("/")[-1]] = i.spec.provider_id.split("/")[-2]

    return instanceIDs

def get_nodeport_services(api_instance):
    nodePorts = []
    api_response = api_instance.list_service_for_all_namespaces()
    for i in api_response.items:
        if i.spec.type == "NodePort" and i.metadata.namespace != "kube-system":
            for port in i.spec.ports:
                nodePorts.append(port.node_port)

    return nodePorts

def create_target_group(client, instanceIDs, port, vpc):
    response = client.create_target_group(
        Name='TG-' + str(port),
        Protocol='TCP_UDP',
        Port=port,
        VpcId=vpc,
        HealthCheckProtocol='TCP',
        HealthCheckPort=str(port),
        TargetType='instance'
    )
    print(str(response))

    targetGroupArn = response['TargetGroups'][0]['TargetGroupArn']

    targets = []
    for instance in instanceIDs:
        targets.append({
            'Id': instance,
            'Port': port
        })

    response = client.register_targets(TargetGroupArn = targetGroupArn, Targets = targets)
    print(str(response))

    return targetGroupArn
    
def handle(event, context):
    urllib3.disable_warnings()
    Configuration = kubernetes.client.Configuration()
    Configuration.host = os.environ['EKS_ENDPOINT_URL']
    Token = os.environ['EKS_BEARER_TOKEN']
    
    Configuration.verify_ssl = False
    Configuration.api_key = {"authorization": "Bearer " + Token}
    kubernetes.client.ApiClient(Configuration)
    api_instance = kubernetes.client.CoreV1Api(kubernetes.client.ApiClient(Configuration))
    instanceIDs = {}
    nodePorts = []

    try:
        instanceIDs = get_nodes(api_instance)
        print(str(instanceIDs))

        nodePorts = get_nodeport_services(api_instance)
        print(str(nodePorts))

    except kubernetes.client.rest.ApiException as e:
        print("Exception when calling CoreV1Api->list_job_for_all_namespaces: %s\n" % e)

    client = boto3.client('elbv2')
    response = client.describe_listeners(LoadBalancerArn=os.environ['AWS_NLB_ARN'])
    listeners = response['Listeners']

    for port in nodePorts:
        target_flag = False
        for listener in listeners:
            if listener['Port'] == port:
                 target_flag = True
                 print("Listner found on same port: " + str(port)) 

        if target_flag == False:
            print("Listner not found on port: " + str(port))
            targetGroupArn = create_target_group(client, instanceIDs, port, os.environ['AWS_NLB_VPC'])
            response = client.create_listener(
                DefaultActions=[{'TargetGroupArn': targetGroupArn, 'Type': 'forward'},], 
                LoadBalancerArn=os.environ['AWS_NLB_ARN'],
                Port=port,
                Protocol='TCP_UDP'
            )
            print(str(response))