FROM amazonlinux:latest

WORKDIR /crypto

# copy main SRC files
COPY /src/main.py /crypto/src/
COPY /src/trail.py /crypto/src/
COPY /src/helper.py /crypto/src/ 
COPY /src/coinbasepro.py /crypto/src/
COPY /src/create-db.py /crypto/src/
COPY /src/crypto_bot_definitions.py /crypto/src/
COPY /src/requirements.txt /crypto/src/

# copy settings files
COPY ./conf/settings.ini /crypto/conf/
COPY ./conf/logger.ini /crypto/conf/

# update yum
RUN yum -y update
RUN yum install -y procps


# install pip & other local dependencies
RUN yum install -y python3-pip
RUN pip3 install --upgrade pip
RUN yum install -y cronie

# install python packages using pip
COPY /src/requirements.txt /crypto/src/
RUN pip3 install -r /crypto/src/requirements.txt

# prettify our prompt and create helpful aliases
RUN echo 'PS1="\[$(tput setaf 3)$(tput bold)[\]appname@\\h$:\\w]#\[$(tput sgr0) \]"' >> /root/.bashrc
RUN echo "alias ll='ls -l'" >> /root/.bashrc

# create log directory
RUN mkdir log

# make scripts executable
RUN chmod +x /crypto/src/main.py
RUN chmod +x /crypto/src/trail.py
RUN chmod +x /crypto/src/helper.py
RUN chmod +x /crypto/src/coinbasepro.py
RUN chmod +x /crypto/src/create-db.py
RUN chmod +x /crypto/src/crypto_bot_definitions.py
# RUN chmod +x /sbin/solo

# RUN (crontab -l 2>/dev/null; echo "0 8 * * * source /aws-user-audit/conf/container.env && /sbin/solo -port=3777 /usr/bin/python3 /aws-user-audit/aws_user_audit.py") | crontab -

# RUN systemctl enable crond.service

ENTRYPOINT ["crond", "-n"]

