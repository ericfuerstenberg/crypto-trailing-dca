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

# install pip & other local dependencies
RUN yum install -y \
        python3-pip
RUN pip3 install --upgrade pip
RUN yum install -y cronie

# install python packages using pip
COPY /src/requirements.txt /crypto/src/
RUN pip3 install -r /crypto/src/requirements.txt

# create log directory
RUN mkdir log

# #set env variable for https proxy to allow communication with workday
# ENV HTTPS_PROXY=http://<PROXY_USERNAME>:<PROXY_PASSWORD>@web-proxy-vip.prod.box.net:3128 
# ENV AWS_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

# set cronjob to run aws_user_audit script 
RUN chmod +x /crypto/src/main.py
RUN chmod +x /crypto/src/trail.py
RUN chmod +x /crypto/src/helper.py
RUN chmod +x /crypto/src/coinbasepro.py
RUN chmod +x /crypto/src/create-db.py
RUN chmod +x /crypto/src/crypto_bot_definitions.py
# RUN chmod +x /sbin/solo

# RUN (crontab -l 2>/dev/null; echo "0 8 * * * source /aws-user-audit/conf/container.env && /sbin/solo -port=3777 /usr/bin/python3 /aws-user-audit/aws_user_audit.py") | crontab -

# RUN systemctl enable crond.service

# ENTRYPOINT ["crond", "-n"]