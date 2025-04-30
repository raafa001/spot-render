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
            cobertura coberturaReportFile: 'target/site/jacoco/jacoco.xml',
                failBuildIfUnhealthy: false,
                failBuildIfTotalCoverageLessThan: 0,
                onlyStable: false,
                sourceRoot: ''
            archiveArtifacts 'target/site/jacoco/*.html, target/site/jacoco/*.csv'
        }
    }
}
