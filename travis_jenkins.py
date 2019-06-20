#!/usr/bin/env python

# need pip installed version of python-jenkins > 0.4.0

import jenkins
import urllib
import urllib2
import json
import time
import os
import re
import sys

from os import environ as env

CONFIGURE_XML = '''<?xml version='1.0' encoding='UTF-8'?>
<project>
  <actions/>
  <description>
     &lt;h4&gt;
     This is jenkins buildfirm for &lt;a href=http://github.com/%(TRAVIS_REPO_SLUG)s&gt;http://github.com/%(TRAVIS_REPO_SLUG)s&lt;/a&gt;&lt;br/&gt;
     see &lt;a href=http://travis-ci.org/%(TRAVIS_REPO_SLUG)s&gt;http://travis-ci.org/%(TRAVIS_REPO_SLUG)s&lt;/a&gt; for travis page that execute this job.&lt;br&gt;
     &lt;/h4&gt;
  </description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <jenkins.model.BuildDiscarderProperty>
      <strategy class="hudson.tasks.LogRotator">
        <daysToKeep>3</daysToKeep>
        <numToKeep>%(NUMBER_OF_LOGS_TO_KEEP)s</numToKeep>
        <artifactDaysToKeep>-1</artifactDaysToKeep>
        <artifactNumToKeep>-1</artifactNumToKeep>
      </strategy>
    </jenkins.model.BuildDiscarderProperty>
    <hudson.model.ParametersDefinitionProperty>
      <parameterDefinitions>
        <hudson.model.TextParameterDefinition>
          <name>TRAVIS_JENKINS_UNIQUE_ID</name>
          <description></description>
          <defaultValue></defaultValue>
        </hudson.model.TextParameterDefinition>
        <hudson.model.TextParameterDefinition>
          <name>TRAVIS_PULL_REQUEST</name>
          <description></description>
          <defaultValue></defaultValue>
        </hudson.model.TextParameterDefinition>
        <hudson.model.TextParameterDefinition>
          <name>TRAVIS_COMMIT</name>
          <description></description>
          <defaultValue></defaultValue>
        </hudson.model.TextParameterDefinition>
      </parameterDefinitions>
    </hudson.model.ParametersDefinitionProperty>
  </properties>
  <scm class='hudson.scm.NullSCM'/>
  <assignedNode>master</assignedNode>
  <canRoam>true</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
  <triggers/>
  <concurrentBuild>true</concurrentBuild>
  <builders>
    <hudson.tasks.Shell>
      <command>
set -x
set -e
env
WORKSPACE=`pwd`
[ "${BUILD_TAG}" = "" ] &amp;&amp; BUILD_TAG="build_tag" # jenkins usually has build_tag environment, note this is sh
trap "pwd; rm -fr $WORKSPACE/${BUILD_TAG} || echo 'ok'" EXIT

# try git clone until success
until git clone https://github.com/%(TRAVIS_REPO_SLUG)s ${BUILD_TAG}/%(TRAVIS_REPO_SLUG)s
do
  echo "Retrying"
done
cd ${BUILD_TAG}/%(TRAVIS_REPO_SLUG)s
#git fetch -q origin '+refs/pull/*:refs/remotes/pull/*'
#git checkout -qf %(TRAVIS_COMMIT)s || git checkout -qf pull/${TRAVIS_PULL_REQUEST}/head
if [ "${TRAVIS_PULL_REQUEST}" != "false" ]; then
 git fetch -q origin +refs/pull/${TRAVIS_PULL_REQUEST}/merge
 git checkout -qf FETCH_HEAD
else
 git checkout -qf ${TRAVIS_COMMIT}
fi

git submodule init
git submodule update

if [ "%(REPOSITORY_NAME)s" = "jsk_travis" ]; then
  mkdir .travis; cp -r * .travis # need to copy, since directory starting from . is ignoreed by catkin build
fi

# run docker build
docker build -t %(DOCKER_IMAGE_JENKINS)s --build-arg CACHEBUST=$(date +%%Y%%m%%d) -f docker/Dockerfile.%(DOCKER_IMAGE_JENKINS)s docker

# run watchdog for kill orphan docker container
.travis/travis_watchdog.py %(DOCKER_CONTAINER_NAME)s &amp;

docker stop %(DOCKER_CONTAINER_NAME)s || echo "docker stop %(DOCKER_CONTAINER_NAME)s ends with $?"
docker rm %(DOCKER_CONTAINER_NAME)s || echo  "docker rm %(DOCKER_CONTAINER_NAME)s ends with $?"
docker pull %(DOCKER_IMAGE_JENKINS)s || true
docker run %(DOCKER_RUN_OPTION)s \\
    --name %(DOCKER_CONTAINER_NAME)s \\
    -e ROS_DISTRO='%(ROS_DISTRO)s' \\
    -e USE_DEB='%(USE_DEB)s' \\
    -e TRAVIS_REPO_SLUG='%(TRAVIS_REPO_SLUG)s' \\
    -e EXTRA_DEB='%(EXTRA_DEB)s' \\
    -e TARGET_PKGS='%(TARGET_PKGS)s' \\
    -e BEFORE_SCRIPT='%(BEFORE_SCRIPT)s' \\
    -e TEST_PKGS='%(TEST_PKGS)s' \\
    -e NOT_TEST_INSTALL='%(NOT_TEST_INSTALL)s' \\
    -e ROS_PARALLEL_JOBS='%(ROS_PARALLEL_JOBS)s' \\
    -e CATKIN_PARALLEL_JOBS='%(CATKIN_PARALLEL_JOBS)s' \\
    -e CATKIN_TOOLS_BUILD_OPTIONS='%(CATKIN_TOOLS_BUILD_OPTIONS)s' \\
    -e CATKIN_TOOLS_CONFIG_OPTIONS='%(CATKIN_TOOLS_CONFIG_OPTIONS)s' \\
    -e ROS_PARALLEL_TEST_JOBS='%(ROS_PARALLEL_TEST_JOBS)s' \\
    -e CATKIN_PARALLEL_TEST_JOBS='%(CATKIN_PARALLEL_TEST_JOBS)s' \\
    -e CMAKE_DEVELOPER_ERROR='%(CMAKE_DEVELOPER_ERROR)s' \\
    -e BUILD_PKGS='%(BUILD_PKGS)s' \\
    -e ROS_REPOSITORY_PATH='%(ROS_REPOSITORY_PATH)s'  \\
    -e ROSDEP_ADDITIONAL_OPTIONS='%(ROSDEP_ADDITIONAL_OPTIONS)s'  \\
    -e DOCKER_RUN_OPTION='%(DOCKER_RUN_OPTION)s'  \\
    -e HOME=/workspace \\
    -v $WORKSPACE/${BUILD_TAG}:/workspace \\
    -v /data/cache/ccache:/workspace/.ccache \\
    -v /data/cache/pip-cache:/root/.cache/pip \\
    -v /data/cache/ros:/workspace/.ros \\
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \\
    -w /workspace %(DOCKER_IMAGE_JENKINS)s /bin/bash \\
    -c "$(cat &lt;&lt;EOL

cd %(TRAVIS_REPO_SLUG)s
set -x
trap 'exit 1' ERR
env

mkdir log
export ROS_LOG_DIR=\$PWD/log
sudo apt-get update -qq || echo Ignore error of apt-get update
sudo apt-get install -qq -y curl git wget sudo lsb-release ccache apt-cacher-ng patch

# setup ccache
sudo ccache -M 30G                   # set maximum size of ccache to 30G

# Enable apt-cacher-ng to cache apt packages
echo 'Acquire::http {proxy "http://$(ifdata -pa docker0):3142"; };' | sudo tee /etc/apt/apt.conf.d/02proxy.conf
sudo apt-get update -qq || echo Ignore error of apt-get update
export SHELL=/bin/bash

# Remove warning about camera module
# Reference: http://stackoverflow.com/questions/12689304/ctypes-error-libdc1394-error-failed-to-initialize-libdc1394
sudo ln /dev/null /dev/raw1394

# setup virtual display for GUI testing
# based on http://wiki.ros.org/docker/Tutorials/GUI
export QT_X11_NO_MITSHM=1
export DISPLAY=:0
sudo apt-get install -qq -y mesa-utils
glxinfo | grep GLX || echo "OK"

# start testing
`cat .travis/travis.sh`

EOL
)"

     </command>
    </hudson.tasks.Shell>
  </builders>
  <publishers/>
  <buildWrappers>
    <hudson.plugins.timestamper.TimestamperBuildWrapper plugin="timestamper@1.5.15"/>
    <hudson.plugins.ansicolor.AnsiColorBuildWrapper plugin="ansicolor@%(ANSICOLOR_PLUGIN_VERSION)s">
      <colorMapName>xterm</colorMapName>
    </hudson.plugins.ansicolor.AnsiColorBuildWrapper>
    <hudson.plugins.build__timeout.BuildTimeoutWrapper plugin="build-timeout@%(TIMEOUT_PLUGIN_VERSION)s">
      <strategy class="hudson.plugins.build_timeout.impl.AbsoluteTimeOutStrategy">
        <timeoutMinutes>120</timeoutMinutes>
      </strategy>
      <operationList>
        <hudson.plugins.build__timeout.operations.FailOperation/>
      </operationList>
    </hudson.plugins.build__timeout.BuildTimeoutWrapper>
  </buildWrappers>
</project>'''

BUILD_SET_CONFIG= 'job/%(name)s/%(number)d/configSubmit'

class Jenkins(jenkins.Jenkins):
    # http://blog.keshi.org/hogememo/2012/12/14/jenkins-setting-build-info
    def set_build_config(self, name, number, display_name, description): # need to allow anonymous user to update build 
        try:
            # print '{{ "displayName": "{}", "description": "{}" }}'.format(display_name, description)
            response = self.jenkins_open(urllib2.Request(
                self.server + BUILD_SET_CONFIG % locals(),
                urllib.urlencode({'json': '{{ "displayName": "{}", "description": "{}" }}'.format(display_name, description)})
                ))
            if response:
                return response
            else:
                raise jenkins.JenkinsException('job[%s] number[%d] does not exist'
                                       % (name, number))
        except urllib2.HTTPError:
            raise jenkins.JenkinsException('job[%s] number[%d] does not exist'
                                   % (name, number))
        except ValueError:
            raise jenkins.JenkinsException(
                'Could not parse JSON info for job[%s] number[%d]'
                % (name, number)
            )

# set build configuration
def set_build_configuration(name, number):
    global j

def wait_for_finished(name, number):
    global j
    sleep = 30
    display = 300
    loop = 0
    result = None
    while True :
        now = time.time() * 1000
        try:
            info = j.get_build_info(name, number)
        except jenkins.NotFoundException, e:
            print('ERROR: Jenkins job name={0}, number={1} in server={2}'
                  'not found.'.format(name, number, j.server))
            break
        except jenkins.JenkinsException, e:
            print('ERROR: Maybe Jenkins server is down. Please visit {0}'
                  .format(j.server))
            break
        except Exception, e:
            print('ERROR: Unexpected error: {0}'.format(e))
            break
        if not info['building']:
            result = info['result']
            break
        # update progressbar
        progress = (now - info['timestamp']) / info['estimatedDuration']
        if loop % (display/sleep) == 0:
            print info['url'], "building: ", info['building'], "result: ", info['result'], "progress: ", progress
        time.sleep(sleep)
        loop += 1
    return result

def wait_for_building(name, number):
    global j
    sleep = 30
    display = 300
    loop = 0
    start_building = None
    while True:
        try:
            j.get_build_info(name,number)
            start_building = True
            return
        except:
            pass
        if loop % (display/sleep) == 0:
            print('wait for {} {}'.format(name, number))
        time.sleep(sleep)
        loop += 1

##
TRAVIS_BRANCH = env.get('TRAVIS_BRANCH')
TRAVIS_COMMIT = env.get('TRAVIS_COMMIT', 'HEAD')
TRAVIS_PULL_REQUEST = env.get('TRAVIS_PULL_REQUEST', 'false')
TRAVIS_REPO_SLUG = env.get('TRAVIS_REPO_SLUG', 'jsk-ros-pkg/jsk_travis')
TRAVIS_BUILD_ID = env.get('TRAVIS_BUILD_ID')
TRAVIS_BUILD_NUMBER = env.get('TRAVIS_BUILD_NUMBER')
TRAVIS_JOB_ID = env.get('TRAVIS_JOB_ID')
TRAVIS_JOB_NUMBER = env.get('TRAVIS_JOB_NUMBER')
ROS_DISTRO = env.get('ROS_DISTRO', 'indigo')
USE_DEB = env.get('USE_DEB', 'true')
EXTRA_DEB = env.get('EXTRA_DEB', '')
TEST_PKGS = env.get('TEST_PKGS', '')
TARGET_PKGS = env.get('TARGET_PKGS', '')
BEFORE_SCRIPT = env.get('BEFORE_SCRIPT', '')
NOT_TEST_INSTALL = env.get('NOT_TEST_INSTALL', '')
ROS_PARALLEL_JOBS = env.get('ROS_PARALLEL_JOBS', '')
CATKIN_PARALLEL_JOBS = env.get('CATKIN_PARALLEL_JOBS', '')
CATKIN_TOOLS_BUILD_OPTIONS = env.get('CATKIN_TOOLS_BUILD_OPTIONS', '')
CATKIN_TOOLS_CONFIG_OPTIONS = env.get('CATKIN_TOOLS_CONFIG_OPTIONS', '')
ROS_PARALLEL_TEST_JOBS = env.get('ROS_PARALLEL_TEST_JOBS', '')
CATKIN_PARALLEL_TEST_JOBS = env.get('CATKIN_PARALLEL_TEST_JOBS', '')
CMAKE_DEVELOPER_ERROR = env.get('CMAKE_DEVELOPER_ERROR', '')
BUILD_PKGS = env.get('BUILD_PKGS', '')
ROS_REPOSITORY_PATH = env.get('ROS_REPOSITORY_PATH', '')
ROSDEP_ADDITIONAL_OPTIONS = env.get('ROSDEP_ADDITIONAL_OPTIONS', '')
DOCKER_CONTAINER_NAME = '_'.join([TRAVIS_REPO_SLUG.replace('/','.'), TRAVIS_JOB_NUMBER])
DOCKER_RUN_OPTION = env.get('DOCKER_RUN_OPTION', '--rm')
NUMBER_OF_LOGS_TO_KEEP = env.get('NUMBER_OF_LOGS_TO_KEEP', '3')
REPOSITORY_NAME = env.get('REPOSITORY_NAME', '')
TRAVIS_BUILD_WEB_URL = env.get('TRAVIS_BUILD_WEB_URL', '')
TRAVIS_JOB_WEB_URL = env.get('TRAVIS_JOB_WEB_URL', '')

print('''
TRAVIS_BRANCH        = %(TRAVIS_BRANCH)s
TRAVIS_COMMIT        = %(TRAVIS_COMMIT)s
TRAVIS_PULL_REQUEST  = %(TRAVIS_PULL_REQUEST)s
TRAVIS_REPO_SLUG     = %(TRAVIS_REPO_SLUG)s
TRAVIS_BUILD_ID      = %(TRAVIS_BUILD_ID)s
TRAVIS_BUILD_NUMBER  = %(TRAVIS_BUILD_NUMBER)s
TRAVIS_JOB_ID        = %(TRAVIS_JOB_ID)s
TRAVIS_JOB_NUMBER    = %(TRAVIS_JOB_NUMBER)s
TRAVIS_BRANCH        = %(TRAVIS_BRANCH)s
ROS_DISTRO       = %(ROS_DISTRO)s
USE_DEB          = %(USE_DEB)s
EXTRA_DEB        = %(EXTRA_DEB)s
TEST_PKGS        = %(TEST_PKGS)s
TARGET_PKGS       = %(TARGET_PKGS)s
BEFORE_SCRIPT      = %(BEFORE_SCRIPT)s
NOT_TEST_INSTALL = %(NOT_TEST_INSTALL)s
ROS_PARALLEL_JOBS       = %(ROS_PARALLEL_JOBS)s
CATKIN_PARALLEL_JOBS    = %(CATKIN_PARALLEL_JOBS)s
CATKIN_TOOLS_BUILD_OPTIONS    = %(CATKIN_TOOLS_BUILD_OPTIONS)s
CATKIN_TOOLS_CONFIG_OPTIONS    = %(CATKIN_TOOLS_CONFIG_OPTIONS)s
ROS_PARALLEL_TEST_JOBS  = %(ROS_PARALLEL_TEST_JOBS)s
CATKIN_PARALLEL_TEST_JOBS = %(CATKIN_PARALLEL_TEST_JOBS)s
CMAKE_DEVELOPER_ERROR  = %(CMAKE_DEVELOPER_ERROR)s
BUILD_PKGS       = %(BUILD_PKGS)s
ROS_REPOSITORY_PATH = %(ROS_REPOSITORY_PATH)s
ROSDEP_ADDITIONAL_OPTIONS = %(ROSDEP_ADDITIONAL_OPTIONS)s
DOCKER_CONTAINER_NAME   = %(DOCKER_CONTAINER_NAME)s
DOCKER_RUN_OPTION = %(DOCKER_RUN_OPTION)s
NUMBER_OF_LOGS_TO_KEEP = %(NUMBER_OF_LOGS_TO_KEEP)s
REPOSITORY_NAME = %(REPOSITORY_NAME)s
TRAVIS_BUILD_WEB_URL = %(TRAVIS_BUILD_WEB_URL)s
TRAVIS_JOB_WEB_URL = %(TRAVIS_JOB_WEB_URL)s
''' % locals())

if env.get('ROS_DISTRO') == 'hydro':
    LSB_RELEASE = '12.04'
    UBUNTU_DISTRO = 'precise'
elif env.get('ROS_DISTRO') in ['indigo', 'jade']:
    LSB_RELEASE = '14.04'
    UBUNTU_DISTRO = 'trusty'
elif env.get('ROS_DISTRO') in ['kinetic', 'lunar']:
    LSB_RELEASE = '16.04'
    UBUNTU_DISTRO = 'xenial'
elif env.get('ROS_DISTRO') in ['melodic']:
    LSB_RELEASE = '18.04'
    UBUNTU_DISTRO = 'bionic'
else:
    LSB_RELEASE = '14.04'
    UBUNTU_DISTRO = 'trusty'

DOCKER_IMAGE_JENKINS = env.get('DOCKER_IMAGE_JENKINS', 'ros-ubuntu:%s' % LSB_RELEASE)

### start here
j = Jenkins('http://jenkins.jsk.imi.i.u-tokyo.ac.jp:8080/', 'k-okada', '11402334328fd5a26f0092c1d763f67f52')

# use snasi color
if j.get_plugin_info('ansicolor'):
    ANSICOLOR_PLUGIN_VERSION=j.get_plugin_info('ansicolor')['version']
else:
    print('you need to install ansi color plugin')
# use timeout plugin
if j.get_plugin_info('build-timeout'):
    TIMEOUT_PLUGIN_VERSION=j.get_plugin_info('build-timeout')['version']
else:
    print('you need to install build_timeout plugin')
# set job_name
job_name = TRAVIS_REPO_SLUG

job_name = re.sub(r'[^0-9A-Za-z]+', '-', job_name)
# filename must be within 255
if len(job_name) >= 128 : # 'jenkins+ job_naem + TRAVIS_REPO_SLUG'
    import hashlib
    m = hashlib.md5()
    m.update(job_name)
    job_name=job_name[:128]+'-'+m.hexdigest()

if j.job_exists(job_name) is None:
    j.create_job(job_name, jenkins.EMPTY_CONFIG_XML)

## if reconfigure job is already in queue, wait for more seconds...
while [item for item in j.get_queue_info() if item['task']['name'] == job_name]:
    time.sleep(10)
# reconfigure job
j.reconfig_job(job_name, CONFIGURE_XML % locals())

## get next number and run
build_number = j.get_job_info(job_name)['nextBuildNumber']
TRAVIS_JENKINS_UNIQUE_ID='{}.{}'.format(TRAVIS_JOB_ID,time.time())

j.build_job(job_name, {'TRAVIS_JENKINS_UNIQUE_ID':TRAVIS_JENKINS_UNIQUE_ID, 'TRAVIS_PULL_REQUEST':TRAVIS_PULL_REQUEST, 'TRAVIS_COMMIT':TRAVIS_COMMIT})
print('next build number is {}'.format(build_number))

## wait for starting
result = wait_for_building(job_name, build_number)
print('start building, wait for result....')

## configure description
if TRAVIS_PULL_REQUEST != 'false':
    github_link = 'github <a href=http://github.com/%(TRAVIS_REPO_SLUG)s/pull/%(TRAVIS_PULL_REQUEST)s>PR #%(TRAVIS_PULL_REQUEST)s</a><br>'
elif TRAVIS_BRANCH:
    github_link = 'github <a href=http://github.com/%(TRAVIS_REPO_SLUG)s/tree/%(TRAVIS_BRANCH)s>http://github.com/%(TRAVIS_REPO_SLUG)s</a><br>'
else:
    github_link = 'github <a href=http://github.com/%(TRAVIS_REPO_SLUG)s>http://github.com/%(TRAVIS_REPO_SLUG)s</a><br>'

if TRAVIS_BUILD_WEB_URL and TRAVIS_JOB_WEB_URL:
    travis_link = 'travis <a href=%(TRAVIS_BUILD_WEB_URL)s>Build #%(TRAVIS_BUILD_NUMBER)s</a> '+ '<a href=%(TRAVIS_JOB_WEB_URL)s>Job #%(TRAVIS_JOB_NUMBER)s</a><br>'
else:
    travis_link = 'travis <a href=http://travis-ci.org/%(TRAVIS_REPO_SLUG)s/>%(TRAVIS_REPO_SLUG)s</a><br>'
j.set_build_config(job_name, build_number, '#%(build_number)s %(TRAVIS_REPO_SLUG)s' % locals(),
                   (travis_link + ' \
       Parameters are<br> \
       ROS_DISTRO = %(ROS_DISTRO)s<br> \
       USE_DEB    = %(USE_DEB)s<br> \
       EXTRA_DEB  = %(EXTRA_DEB)s<br> \
       TARGET_PKGS = %(TARGET_PKGS)s<br> \
       BEFORE_SCRIPT = %(BEFORE_SCRIPT)s<br> \
       TEST_PKGS  = %(TEST_PKGS)s<br> \
       NOT_TEST_INSTALL = %(NOT_TEST_INSTALL)s<br> \
       ROS_PARALLEL_JOBS = %(ROS_PARALLEL_JOBS)s<br> \
       CATKIN_PARALLEL_JOBS = %(CATKIN_PARALLEL_JOBS)s<br> \
       CATKIN_TOOLS_BUILD_OPTIONS = %(CATKIN_TOOLS_BUILD_OPTIONS)s<br> \
       CATKIN_TOOLS_CONFIG_OPTIONS = %(CATKIN_TOOLS_CONFIG_OPTIONS)s<br> \
       ROS_PARALLEL_TEST_JOBS = %(ROS_PARALLEL_TEST_JOBS)s<br> \
       CATKIN_PARALLEL_TEST_JOBS = %(CATKIN_PARALLEL_TEST_JOBS)s<br> \
       CMAKE_DEVELOPER_ERROR = %(CMAKE_DEVELOPER_ERROR)s<br> \
       BUILDING_PKG = %(BUILD_PKGS)s<br> \
       ROS_REPOSITORY_PATH = %(ROS_REPOSITORY_PATH)s<br> \
       ROSDEP_ADDITIONAL_OPTIONS = %(ROSDEP_ADDITIONAL_OPTIONS)s<br> \
       DOCKER_RUN_OPTION = %(DOCKER_RUN_OPTION)s<br> \
') % locals())

## wait for result
result = wait_for_finished(job_name, build_number)

## show console
print j.get_build_console_output(job_name, build_number)
print "======================================="
print j.get_build_info(job_name, build_number)['url']
print "======================================="
if result == "SUCCESS" :
    exit(0)
else:
    exit(1)


