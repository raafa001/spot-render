pipeline {
    agent any
    environment {
        AWS_REGION = 'us-east-1'
    }
    parameters {
        choice(name: 'TERRAFORM_ACTION',
            choices: ['plan', 'apply', 'destroy'],
            description: 'Escolha a ação do Terraform a ser executada')
        extendedChoice(name: 'TERRAFORM_DIRECTORIES',
            type: 'PT_CHECKBOX', // Ou 'PT_MULTI_SELECT' para uma lista suspensa com seleção múltipla
            value: 'kubernetes,network,permissions,s3', // Opções separadas por vírgula
            multiSelectDelimiter: ',',
            description: 'Selecione os diretórios Terraform para executar a ação (marque as caixas desejadas)')
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
                        params.TERRAFORM_DIRECTORIES.split(',').each { tf_dir ->
                            echo "------------------- Terraform Plan: ${tf_dir.trim()} -------------------"
                            sh "cd terraform/${tf_dir.trim()} && terraform init"
                            sh "cd terraform/${tf_dir.trim()} && terraform plan -no-color -out=${tf_dir.trim()}.plan"
                            archiveArtifacts "terraform/${tf_dir.trim()}/*.plan"
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
                        params.TERRAFORM_DIRECTORIES.split(',').each { tf_dir ->
                            echo "------------------- Terraform ${params.TERRAFORM_ACTION}: ${tf_dir.trim()} -------------------"
                            sh "cd terraform/${tf_dir.trim()} && terraform init"
                            if (params.TERRAFORM_ACTION == 'apply') {
                                sh "cd terraform/${tf_dir.trim()} && terraform apply -auto-approve ${tf_dir.trim()}.plan"
                            } else if (params.TERRAFORM_ACTION == 'destroy') {
                                sh "cd terraform/${tf_dir.trim()} && terraform destroy -auto-approve"
                            }
                        }
                    }
                }
            }
        }
    }
}