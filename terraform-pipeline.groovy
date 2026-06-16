pipeline {
    agent any

    environment {
        AWS_ACCESS_KEY_ID     = credentials('aws-access-key')
        AWS_SECRET_ACCESS_KEY = credentials('aws-secret-key')
    }

    parameters {
        string(name: 'TERRAFORM_DIRECTORY', defaultValue: '.', description: 'Diretório do Terraform')
        choice(
            name: 'TERRAFORM_ACTION',
            choices: ['plan', 'apply', 'destroy'],
            description: 'Ação do Terraform'
        )
        booleanParam(
            name: 'REQUIRE_APPROVAL',
            defaultValue: true,
            description: 'Requer aprovação manual para apply/destroy'
        )
    }

    stages {
        stage('Validate Directory') {
            steps {
                script {
                    if (!fileExists("${params.TERRAFORM_DIRECTORY}/main.tf")) {
                        error "main.tf não encontrado em ${params.TERRAFORM_DIRECTORY}"
                    }
                }
            }
        }

        stage('Terraform Init') {
            steps {
                dir(params.TERRAFORM_DIRECTORY) {
                    sh 'terraform init -input=false -backend=true -reconfigure'
                }
            }
        }

        stage('Terraform Validate') {
            steps {
                dir(params.TERRAFORM_DIRECTORY) {
                    sh 'terraform validate -no-color'
                }
            }
        }

        stage('Terraform Plan') {
            steps {
                dir(params.TERRAFORM_DIRECTORY) {
                    sh 'terraform plan -no-color -input=false -out=tfplan'
                }
            }
        }

        stage('Require Approval') {
            when {
                expression { params.TERRAFORM_ACTION != 'plan' && params.REQUIRE_APPROVAL }
            }
            steps {
                input message: "Proceed with Terraform ${params.TERRAFORM_ACTION}?", ok: 'Proceed'
            }
        }

        stage('Terraform Apply/Destroy') {
            when {
                expression { params.TERRAFORM_ACTION == 'apply' || params.TERRAFORM_ACTION == 'destroy' }
            }
            steps {
                dir(params.TERRAFORM_DIRECTORY) {
                    script {
                        if (params.TERRAFORM_ACTION == 'apply') {
                            sh 'terraform apply -auto-approve -input=false tfplan'
                        } else {
                            sh 'terraform destroy -auto-approve -input=false'
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo "Terraform ${params.TERRAFORM_ACTION} concluído com sucesso."
        }
        failure {
            echo "Terraform ${params.TERRAFORM_ACTION} falhou."
        }
    }
}
