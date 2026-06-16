pipeline {
    agent any

    parameters {
        string(name: 'GIT_BRANCH', defaultValue: 'main', description: 'Branch do repositório')
        string(name: 'MAVEN_TOOL', defaultValue: 'seu-maven', description: 'Nome da instalação Maven no Jenkins')
        booleanParam(name: 'FAIL_ON_SCAN_ERROR', defaultValue: false, description: 'Falhar o build se algum scan falhar')
    }

    tools {
        maven "${params.MAVEN_TOOL}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: params.GIT_BRANCH ]],
                    userRemoteConfigs: [[
                        url: 'https://github.com/raafa001/spot-render.git',
                        credentialsId: 'github-app'
                    ]]
                ])
            }
        }

        stage('Security Scan') {
            parallel {
                stage('Checkov - Terraform') {
                    steps {
                        script {
                            try {
                                sh "docker run --rm -v \"${WORKSPACE}:/src\" bridgecrew/checkov -d /src --compact"
                            } catch (Exception e) {
                                echo "WARNING: checkov scan failed: ${e}"
                                if (params.FAIL_ON_SCAN_ERROR) {
                                    error "checkov scan failed: ${e}"
                                }
                            }
                        }
                    }
                }

                stage('Hadolint - Dockerfile') {
                    steps {
                        script {
                            try {
                                sh "docker run --rm -v \"${WORKSPACE}:/src\" hadolint/hadolint:latest /src/Dockerfile"
                            } catch (Exception e) {
                                echo "WARNING: hadolint scan failed: ${e}"
                                if (params.FAIL_ON_SCAN_ERROR) {
                                    error "hadolint scan failed: ${e}"
                                }
                            }
                        }
                    }
                }

                stage('Trivy - Kubernetes YAML') {
                    steps {
                        script {
                            try {
                                sh "docker run --rm -v \"${WORKSPACE}:/src\" aquasec/trivy:latest config --severity HIGH,CRITICAL /src/kubernetes"
                            } catch (Exception e) {
                                echo "WARNING: trivy scan failed: ${e}"
                                if (params.FAIL_ON_SCAN_ERROR) {
                                    error "trivy scan failed: ${e}"
                                }
                            }
                        }
                    }
                }

                stage('ShellCheck - Scripts') {
                    steps {
                        script {
                            try {
                                sh "docker run --rm -v \"${WORKSPACE}:/src\" koalaman/shellcheck:latest -a /src/scripts/*.sh"
                            } catch (Exception e) {
                                echo "WARNING: shellcheck scan failed: ${e}"
                                if (params.FAIL_ON_SCAN_ERROR) {
                                    error "shellcheck scan failed: ${e}"
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
            echo 'Todos os scans de segurança foram concluídos com sucesso.'
        }
        failure {
            echo 'Um ou mais scans de segurança falharam.'
        }
    }
}
