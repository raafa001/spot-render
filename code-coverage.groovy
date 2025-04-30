pipeline {
    agent any
    tools {
        maven 'seu-maven'
    }
    stages {
        stage('Checkout') {
            steps {
                git branch: 'main',
                    credentialsId: 'github-app',
                    url: 'https://github.com/raafa001/spot-render.git'
            }
        }
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
    }
    post {
        always {
            steps { // Adicione este bloco steps
                cobertura coberturaReportFile: 'target/site/jacoco/jacoco.xml',
                    failUnhealthy: false,
                    conditionalCoverageTargets: '0',
                    onlyStable: false
                archiveArtifacts 'target/site/jacoco/*.html, target/site/jacoco/*.csv'
            }
        }
    }
}
