FROM quay.io/jupyter/base-notebook

USER root

RUN apt-get update && apt-get install -yq --no-install-recommends \
    build-essential \
    python3-pip

# add the bash script
ADD install.sh /
# change rights for the script
RUN chmod u+x /install.sh
# run the bash script
RUN /install.sh

# prepend the new path
ENV PATH /root/miniconda3/bin:$PATH
