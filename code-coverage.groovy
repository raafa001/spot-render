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
                echo 'Running security scans using Docker...'

                // Análise de vulnerabilidades para Terraform
                script {
                    try {
                        sh "docker run --rm -v \"${WORKSPACE}:/src\" accurics/tfsec:latest /src"
                    } catch (Exception e) {
                        echo "tfsec scan failed: ${e}"
                        // Adicione lógica para falhar o build se necessário
                    }
                }

                // Análise de linter para Dockerfile
                script {
                    try {
                        sh "docker run --rm -v \"${WORKSPACE}:/src\" hadolint/hadolint:latest /src/Dockerfile"
                    } catch (Exception e) {
                        echo "hadolint scan failed: ${e}"
                        // Adicione lógica para falhar o build se necessário
                    }
                }

                // Análise de vulnerabilidades para Kubernetes YAML
                script {
                    try {
                        sh "docker run --rm -v \"${WORKSPACE}:/src\" aquasec/trivy:latest config /src/kubernetes"
                    } catch (Exception e) {
                        echo "trivy scan failed: ${e}"
                        // Adicione lógica para falhar o build se necessário
                    }
                }

                // Análise de linter para Shell Scripts
                script {
                    try {
                        sh "docker run --rm -v \"${WORKSPACE}:/src\" koalaman/shellcheck:latest -a /src/*.sh"
                    } catch (Exception e) {
                        echo "shellcheck scan failed: ${e}"
                        // Adicione lógica para falhar o build se necessário
                    }
                }
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
            archiveArtifacts '**/*'
        }
    }
}
