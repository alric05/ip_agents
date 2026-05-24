// @Library('dasl@github_support') _
// Pin to a branch or tag like:
// @Library('dasl@0.0.3')

library(
  identifier: 'dasl@master',
  retriever: modernSCM([
    $class: 'GitSCMSource',
    remote: 'https://github.com/clarivate-prod/ipds-deployment-automation-shared-library.git',
    credentialsId: 'github-app-private-key'
  ])
)

// Invoke library with defaults https://wiki.clarivate.io/pages/viewpage.action?spaceKey=DEVOPS&title=Terraform+Deployment+Automation+-+Jenkins+Shared+Library
//dasl ()

// Invoke with some common parameters. For instance, reducing choices:
dasl (
    env_choices: ["dev-snapshot", "dev-stable", "prod"],
    region_choices: ["us-west-2"],
    custom_gradle_image: 'docker-proxy.repo.clarivate.io/gradle:8.10.1-jdk21',
    default_git_branch: 'master'
)

// More information also in the repository README:
// https://git.clarivate.io/projects/OPDEVOPS/repos/deployment-automation-shared-library/browse/README.md

 