# Karaage3-plugins-project-application
A Project Application plugin for Karaage3.  Captures some basic extra information not in the current application process.

## Karaage
Karaage is a cluster account management tool.

[https://github.com/Karaage-Cluster/karaage]()

[http://karaage.readthedocs.io/en/latest/]()

## Project Application Plugin
Karaage has a plugin framework for adding features.  There is an included *kgapplications* plugin for managing user and project applications ([https://github.com/Karaage-Cluster/karaage/tree/master/karaage/plugins]()).  
This Project Application plugin is separate to the *kgapplications* plugin, and provides more tailored forms.

### Features
Karaage3 has the concept of project leaders, but does not capture who the lead chief investigator is for a project.  Karaage also only records the institute of a project, but not lower level detail such as faculty or department (or their equivalents).
This Project Application is based around accounting for which person, institution, faculty and department are responsible for the project.  This aids usage reporting and data ownership.
The forms ask for more detail than the builtin kgapplications.  This helps with allocating suitable resources.

## Installation
Karaage3 is installed as a (docker) container, and has a configuration file: */etc/karaage3/settings.py*

To install Karaage3 please see:

```
http://karaage.readthedocs.io/en/latest/getting_started.html
```

To include this plugin, create a location for the code, eg (assuming you are installing as root);

```
mkdir -p /usr/local/src/karaage3/plugins/
```

Clone the code;

```
cd /usr/local/src/karaage3/plugins/
git clone https://github.com/melbournebioinformatics/Karaage3-plugins-project-application.git project_application
```

You will then need to modify the karaage service file and the configuration file to point to where the plugin is.

In

```
/opt/karaage/etc/karaage3/settings.py
```

Add

```
import sys
sys.path.append('/usr/local/src/karaage3/plugins/project_application')

PLUGINS = [
    'karaage.plugins.kgapplications.plugin',
    'project_application.plugin',
]
```

To make the code visible to the karaage container, you will need to add the path to the karaage container service, eg;

> Original
> 
> ```
ExecStart=/usr/bin/docker run --name karaage \
  --net="host" \
  -v /etc/passwd:/etc/passwd \
  -v /etc/group:/etc/group \
  -v /opt/karaage/etc/munge:/etc/munge \
  -v /opt/karaage/log/munge:/var/log/munge \
  -v /opt/karaage/lib/munge:/var/lib/munge \
  -v /opt/karaage/etc/slurm:/usr/local/etc \
  -v /opt/karaage/etc/shibboleth:/etc/shibboleth \
  -v /opt/karaage/etc/karaage3:/etc/karaage3 \
  -v /opt/karaage/log/apache2:/var/log/apache2 \
  -v /opt/karaage/log/karaage3:/var/log/karaage3 \
  -v /opt/karaage/lib/karaage3:/var/lib/karaage3 \
  -v /opt/karaage/cache/karaage3:/var/cache/karaage3 \
```

Added

```
  -v /usr/local/src/karaage3/plugins:/usr/local/src/karaage3/plugins \
```

> Original
> 
> ```
  -v /var/run/mysqld:/var/run/mysqld \
  brianmay/karaage:slurm17.02-apache
```
