// OBSOLETO - Jenkins removido/desativado
// Substituido por: .github/workflows/terraform-automation.yml
// Mantido apenas como referencia.

pipeline {
    agent any

    environment {
        AWS_REGION = 'us-east-1'
    }

    parameters {
        choice(
            name: 'TERRAFORM_ACTION',
            choices: ['plan', 'apply', 'destroy'],
            description: 'Escolha a ação do Terraform a ser executada'
        )
        extendedChoice(
            name: 'TERRAFORM_DIRECTORIES',
            type: 'PT_CHECKBOX',
            value: 'kubernetes,network,permissions,s3',
            multiSelectDelimiter: ',',
            description: 'Selecione os diretórios Terraform para executar a ação'
        )
        booleanParam(
            name: 'REQUIRE_APPROVAL',
            defaultValue: true,
            description: 'Requer aprovação manual antes de apply/destroy'
        )
    }

    stages {
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
                    userRemoteConfigs: [[
                        url: 'https://github.com/raafa001/spot-render.git',
                        credentialsId: 'github-app'
                    ]]
                ])
            }
        }

        stage('Validate Parameters') {
            steps {
                script {
                    def dirs = params.TERRAFORM_DIRECTORIES.split(',')
                    def validDirs = ['kubernetes', 'network', 'permissions', 's3']
                    dirs.each { dir ->
                        if (!validDirs.contains(dir.trim())) {
                            error "Diretório inválido: ${dir.trim()}. Válidos: ${validDirs}"
                        }
                    }
                }
            }
        }

        stage('Terraform Init') {
            steps {
                script {
                    params.TERRAFORM_DIRECTORIES.split(',').each { tf_dir ->
                        dir("terraform/${tf_dir.trim()}") {
                            withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                sh 'terraform init -input=false -backend=true -reconfigure'
                            }
                        }
                    }
                }
            }
        }

        stage('Terraform Validate') {
            steps {
                script {
                    params.TERRAFORM_DIRECTORIES.split(',').each { tf_dir ->
                        dir("terraform/${tf_dir.trim()}") {
                            sh 'terraform validate -no-color'
                        }
                    }
                }
            }
        }

        stage('Terraform Plan') {
            when {
                expression { params.TERRAFORM_ACTION == 'plan' }
            }
            steps {
                script {
                    params.TERRAFORM_DIRECTORIES.split(',').each { tf_dir ->
                        dir("terraform/${tf_dir.trim()}") {
                            withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                echo "Terraform Plan: ${tf_dir.trim()}"
                                sh "terraform plan -no-color -input=false -out=${tf_dir.trim()}.plan"
                                archiveArtifacts artifacts: "${tf_dir.trim()}.plan", allowEmptyArchive: true
                            }
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
                input message: 'Aprovar a aplicação/destruição da infraestrutura Terraform?', ok: 'Aprovar'
            }
        }

        stage('Terraform Apply/Destroy') {
            when {
                expression { params.TERRAFORM_ACTION == 'apply' || params.TERRAFORM_ACTION == 'destroy' }
            }
            steps {
                script {
                    params.TERRAFORM_DIRECTORIES.split(',').each { tf_dir ->
                        dir("terraform/${tf_dir.trim()}") {
                            withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                echo "Terraform ${params.TERRAFORM_ACTION}: ${tf_dir.trim()}"
                                if (params.TERRAFORM_ACTION == 'apply') {
                                    sh "terraform apply -auto-approve -input=false ${tf_dir.trim()}.plan"
                                } else {
                                    sh "terraform destroy -auto-approve -input=false"
                                }
                            }
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
