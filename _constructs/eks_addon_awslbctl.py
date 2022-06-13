import json
from constructs import Construct
from aws_cdk import aws_iam
from aws_cdk import aws_eks


class AwsLoadBalancerController(Construct):
    # ----------------------------------------------------------
    # AWS LoadBalancer Controllerをdeployする
    # IngressのannotationでALBを作成する
    # ----------------------------------------------------------

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id)

        self.check_parameter(kwargs)
        self.region = kwargs.get('region')
        self.vpc_id = kwargs.get('vpc_id')
        self.cluster: aws_eks.Cluster = kwargs.get('cluster')

    def deploy(self, dependency: Construct) -> Construct:
        # ----------------------------------------------------------
        # AWS LoadBalancer Controller for AWS ALB
        #   - Service Account
        #   - Namespace: kube-system
        #   - Deployment
        #   - Service
        # ----------------------------------------------------------
        awslbcontroller_sa = self.cluster.add_service_account(
            'LBControllerServiceAccount',
            name='aws-load-balancer-controller',  # fixed name
            namespace='kube-system',
        )
        if dependency is not None:
            awslbcontroller_sa.node.add_dependency(dependency)

        statements = []
        with open('./policies/awslbcontroller-policy.json') as f:
            data = json.load(f)
            for statement in data['Statement']:
                statements.append(aws_iam.PolicyStatement.from_json(statement))

        policy = aws_iam.Policy(
            self, 'AWSLoadBalancerControllerIAMPolicy', statements=statements)
        policy.attach_to_role(awslbcontroller_sa.role)

        aws_lb_controller_chart = self.cluster.add_helm_chart(
            'AwsLoadBalancerController',
            chart='aws-load-balancer-controller',
            release='aws-load-balancer-controller',  # Deployment name
            repository='https://aws.github.io/eks-charts',
            # version=None,
            namespace='kube-system',
            create_namespace=False,
            values={
                'clusterName': self.cluster.cluster_name,
                'region': self.region,
                'vpcId': self.vpc_id,
                'serviceAccount': {
                    'name': awslbcontroller_sa.service_account_name,
                    'create': False,
                    'annotations': {
                        'eks.amazonaws.com/role-arn': awslbcontroller_sa.role.role_arn
                    }
                }
            }
            # timeout=None,
            # wait=None
        )
        aws_lb_controller_chart.node.add_dependency(awslbcontroller_sa)

        return aws_lb_controller_chart

    @staticmethod
    def check_parameter(key):
        if type(key.get('region')) is not str:
            raise TypeError('Must be set region.')
        if key.get('region') == '':
            raise TypeError('Must be set region.')
        if type(key.get('cluster')) is not aws_eks.Cluster:
            raise TypeError('Must be set Cluster.')
