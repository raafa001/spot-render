pipeline {
    agent any
    environment {
        AWS_REGION = 'us-east-1' // Defina sua região da AWS aqui
    }
    parameters {
        choice(name: 'TERRAFORM_ACTION',
            choices: ['plan', 'apply', 'destroy'],
            description: 'Escolha a ação do Terraform a ser executada')
        multipleselect(name: 'TERRAFORM_DIRECTORIES',
            choices: ['kubernetes', 'network', 'permissions', 's3'],
            description: 'Selecione os diretórios Terraform para executar a ação (selecione múltiplos com Ctrl ou Shift)')
        booleanParam(name: 'REQUIRE_APPROVAL',
            defaultValue: true,
            description: 'Requer aprovação manual antes de executar o "apply" ou "destroy"')
    }
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'github-app',
                    url: 'https://github.com/raafa001/spot-render.git'
            }
        }
        stage('Terraform Plan') {
            when {
                expression { params.TERRAFORM_ACTION == 'plan' }
            }
            steps {
                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                    script {
                        params.TERRAFORM_DIRECTORIES.each { tf_dir ->
                            echo "------------------- Terraform Plan: ${tf_dir} -------------------"
                            sh "cd terraform/${tf_dir} && terraform init"
                            sh "cd terraform/${tf_dir} && terraform plan -no-color -out=${tf_dir}.plan"
                            archiveArtifacts "terraform/${tf_dir}/*.plan"
                        }
                    }
                }
            }
        }
        stage('Require Approval') {
            when {
                expression { params.TERRAFORM_ACTION != 'plan' && params.REQUIRE_APPROVAL }
            }
            steps {
                input message: 'Aprovar a aplicação/destruição da infraestrutura Terraform selecionada?', ok: 'Aprovar'
            }
        }
        stage('Terraform Apply/Destroy') {
            when {
                expression { params.TERRAFORM_ACTION == 'apply' || params.TERRAFORM_ACTION == 'destroy' }
            }
            steps {
                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                    script {
                        params.TERRAFORM_DIRECTORIES.each { tf_dir ->
                            echo "------------------- Terraform ${params.TERRAFORM_ACTION}: ${tf_dir} -------------------"
                            sh "cd terraform/${tf_dir} && terraform init"
                            if (params.TERRAFORM_ACTION == 'apply') {
                                sh "cd terraform/${tf_dir} && terraform apply -auto-approve ${tf_dir}.plan"
                            } else if (params.TERRAFORM_ACTION == 'destroy') {
                                sh "cd terraform/${tf_dir} && terraform destroy -auto-approve"
                            }
                        }
                    }
                }
            }
        }
    }
}
