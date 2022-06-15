import aws_cdk
from constructs import Construct
from aws_cdk import aws_eks
from aws_cdk import aws_ec2
from aws_cdk import aws_iam
from util.configure.config import Config
from _constructs.eks_addon_awslbctl import AwsLoadBalancerController
from _constructs.eks_addon_extdns import  ExternalDnsController
from _constructs.eks_addon_cwmetrics import CloudWatchContainerInsightsMetrics
from _constructs.eks_addon_cwlogs import CloudWatchContainerInsightsLogs
from _constructs.eks_service_argocd import ArgoCd


# TODO: cdk.jsonの  flask-backendをflask-appに変更する。
#  "flask_backend": {
#           "eks_cluster": "app_eks",
#           "namespace": "flask-backend",
#           "service_account": "flask-backend",
#           "dynamodb_table": "messages",
#           "dynamodb_partition": "uuid"
#  }


class EksCluster(Construct):
    # --------------------------------------------------------------
    # EKS Cluster
    # --------------------------------------------------------------
    def __init__(self, scope: Construct, id: str, config: Config) -> None:
        super().__init__(scope, id)

        self.config: Config = config
        self.cluster: aws_eks.Cluster = None

    def provisioning(self):
        vpc = aws_ec2.Vpc.from_lookup(self, 'VPC1', vpc_name=self.config.vpc.name)

        _owner_role = aws_iam.Role(
            scope=self,
            id='EksClusterOwnerRole',
            role_name=f'{self.config.env.name}EksClusterOwnerRole',
            assumed_by=aws_iam.AccountRootPrincipal())

        print('-------------------------------------------------')
        print(f'Instance Type: {self.config.eks.instance_type}')
        self.cluster = aws_eks.Cluster(
            self,
            'EksCluster',
            cluster_name=self.config.eks.name,
            version=aws_eks.KubernetesVersion.V1_21,
            default_capacity_type=aws_eks.DefaultCapacityType.NODEGROUP,
            default_capacity=1,  # (注)HandonのためWorker Nodeを1にする。
            default_capacity_instance=aws_ec2.InstanceType(self.config.eks.instance_type),
            vpc=vpc,
            masters_role=_owner_role)

        # CI/CDでClusterを作成する際、IAM Userでkubectlを実行する際に追加する。
        # kubectl commandを実行できるIAM Userを追加
        # self.cluster.aws_auth.add_user_mapping(
        #         user=aws_iam.User.from_user_name(
        #                 self, 'K8SUser-yagitatakashi', 'yagitatakashi'),
        #         groups=['system:masters']
        # )

        self.cfn_outputs_eks_cluster_attributes()
        self.deploy_addons()

    def cfn_outputs_eks_cluster_attributes(self):
        _env = self.config.env.name  # dev, gitops
        aws_cdk.CfnOutput(
            self,
            id=f'CfnOutputClusterName',
            value=self.cluster.cluster_name,
            description="Name of EKS Cluster",
            export_name=f'EksClusterName-{_env}'
        )
        aws_cdk.CfnOutput(
            self,
            id=f'CfnOutputKubectlRoleArn',
            value=self.cluster.kubectl_role.role_arn,
            description="Kubectl Role Arn of EKS Cluster",
            export_name=f'EksClusterKubectlRoleArn-{_env}'
        )
        aws_cdk.CfnOutput(
            self,
            id=f'CfnOutputKubectlSecurityGroupId',
            value=self.cluster.kubectl_security_group.security_group_id,
            description="Kubectl Security Group Id of EKS Cluster",
            export_name=f'EksClusterKubectlSecurityGroupId-{_env}'
        )
        aws_cdk.CfnOutput(
            self,
            id=f'CfnOutputOidcProviderArn',
            value=self.cluster.open_id_connect_provider.open_id_connect_provider_arn,
            description="OIDC Provider ARN of EKS Cluster",
            export_name=f'EksClusterOidcProviderArn-{_env}'
        )

    def deploy_addons(self):
        # --------------------------------------------------------------------
        # EKS Add On
        #   - AWS Load Balancer Controller
        #   - External DNS
        #   - CloudWatch Container Insight Metrics
        #   - CloudWatch Container Insight Logs
        # --------------------------------------------------------------------

        dependency = None

        if self.config.eks.addon_enable_awslbclt:
            vpc = aws_ec2.Vpc.from_lookup(self, 'VPC2', vpc_name=self.config.vpc.name)

            alb_ctl = AwsLoadBalancerController(
                self,
                'AwsLbController',
                region=self.config.aws_env.region,
                cluster=self.cluster,
                vpc_id=vpc.vpc_id)
            dependency = alb_ctl.deploy(dependency)

        if self.config.eks.addon_enable_extdns:
            ext_dns = ExternalDnsController(
                self,
                'ExternalDNS',
                region=self.config.aws_env.region,
                cluster=self.cluster)
            dependency = ext_dns.deploy(dependency)

        if self.config.eks.addon_enable_cwmetrics:
            insight_metrics = CloudWatchContainerInsightsMetrics(
                self,
                'CloudWatchInsightsMetrics',
                region=self.config.aws_env.region,
                cluster=self.cluster)
            dependency = insight_metrics.deploy(dependency)

        if self.config.eks.addon_enable_cwlogs:
            insight_logs = CloudWatchContainerInsightsLogs(
                self,
                'CloudWatchInsightLogs',
                region=self.config.aws_env.region,
                cluster=self.cluster)
            dependency = insight_logs.deploy(dependency)

        # if self.config.eks.service_argocd:
        #     argocd = ArgoCd(
        #         self,
        #         'ArgoCd',
        #         region=self.config.aws_env.region,
        #         cluster=self.cluster,
        #         config=self.config
        #     )
        #     dependency = argocd.deploy(dependency)
