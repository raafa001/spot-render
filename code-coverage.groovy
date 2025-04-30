pipeline {
    agent any
    tools {
        maven 'seu-maven' // Substitua pelo nome da sua instalação do Maven
    }
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'github-app',
                    url: 'https://github.com/raafa001/spot-render.git'
            }
        }
        stage('Security Scan') {
            steps {
                echo 'Running security scans...'
                // Análise de vulnerabilidades para Terraform (assumindo arquivos .tf na raiz ou subdiretório 'terraform')
                sh 'if command -v tfsec >/dev/null 2>&1; then find . -name "*.tf" -exec tfsec {} +; else echo "tfsec not found."; fi'

                // Análise de vulnerabilidades para Dockerfile (assumindo Dockerfile na raiz)
                sh 'if command -v hadolint >/dev/null 2>&1; then hadolint Dockerfile; else echo "hadolint not found."; fi'

                // Análise de vulnerabilidades para Kubernetes YAML (assumindo arquivos .yaml ou .yml em 'kubernetes')
                sh 'if command -v trivy >/dev/null 2>&1; then find kubernetes -name "*.yaml" -o -name "*.yml" -exec trivy config {} +; else echo "trivy not found."; fi'

                // Análise de vulnerabilidades para Shell Scripts (assumindo arquivos .sh na raiz ou subdiretório 'scripts')
                sh 'if command -v shellcheck >/dev/null 2>&1; then find . -name "*.sh" -exec shellcheck {} +; else echo "shellcheck not found."; fi'
            }
        }
        // Se você ainda tiver código Java e quiser cobertura:
        /*
        stage('Run Tests') {
            steps {
                sh 'mvn test'
            }
        }
        stage('Code Coverage') {
            steps {
                sh 'mvn jacoco:report'
            }
        }
        */
    }
    post {
        always {
            // Adicione aqui ações pós-build, como arquivar artefatos
            archiveArtifacts '**/*'
        }
    }
}
