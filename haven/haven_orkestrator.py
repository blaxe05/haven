from . import haven_utils as hu
from . import haven_chk as hc
import os
import borgy_job_service_client
import time
import copy
import pandas as pd
import numpy as np 
import getpass
import pprint


def submit_job(command, job_config, workdir, savedir_logs=None):
    """
    Launches a job in borgy

    Parameters
    ----------
    command: str
        command you wish to submit
    job_config: dict
        dictionary that should contain keys that correspond to borgy cli's arguments
    workdir: str
        path to where the borgy should run the code
    savedir_logs: str
        path to where the logs are exported (if needed)

    Example
    -------
        import os
        import haven_jobs_utils as hju
        
        job_config = {'data': ['/mnt:/mnt'],
                'image': 'images.borgy.elementai.net/issam/main',
                'bid': '5',
                'restartable': '1',
                'gpu': '1',
                'mem': '50',
                'cpu': '2'}
                
        command = 'echo $PATH'
        job_id = hju.submit_job(command=command, 
                       job_config=job_config, 
                       workdir=os.path.dirname(os.path.realpath(__file__)))
    """
    eai_command = get_job_command(job_config, command, savedir_logs, workdir)
    job_id = hu.subprocess_call(eai_command).replace("\n", "")

    return job_id


def get_api(username):
    # Get Borgy API
    config = borgy_job_service_client.Configuration()
    config.host = "https://job-service.borgy.elementai.net"

    api_client = borgy_job_service_client.ApiClient(config)

    api_client = borgy_job_service_client.ApiClient(config)
    api_client.set_default_header('X-User', username)

    # create an instance of the API class
    return borgy_job_service_client.JobsApi(api_client)

def get_jobs_dict(api, job_id_list, query_size=20):
    # get jobs
    jobs = []
    for i in range(0, len(job_id_list), query_size):
        job_id_string = "id IN ("
        for job_id in  job_id_list[i:i + query_size]:
            job_id_string += "'%s', " % job_id
        job_id_string = job_id_string[:-2] + ")"
        jobs += api.v1_jobs_get(q=job_id_string)

    jobs_dict = {job.id: job for job in jobs}

    return jobs_dict

def get_job(api, job_id):
    """Get a Borgy job."""
    return api.v1_jobs_job_id_get(job_id)

def get_jobs(api, username):
    return api.v1_jobs_get(
            q="alive=true AND name='{}' "
            "ORDER BY createdOn "
            "DESC LIMIT 1000".format(username))



def get_job_command(job_config, command, savedir, workdir):
    """Compose the borgy submit command."""
    eai_command = "eai job submit "

    # Add the Borgy options
    for k, v in job_config.items():
        if k in ['username']:
            continue
        # Handle all the different type of parameters
        if k == "restartable":
            eai_command += " --%s" % k
        elif k in ["gpu", "cpu", "mem"]:
            eai_command += " --%s=%s" % (k, v)
        elif isinstance(v, list):
            for v_tmp in v:
                eai_command += " --%s %s" % (k, v_tmp)
        elif k in ["userid", "email"]:
            continue
        else:
            eai_command += " --%s %s" % (k, v)
    eai_command += " --workdir %s" % workdir

    # Add the python command to run and the logs file
    if savedir:
        path_log = os.path.join(savedir, "logs.txt")
        path_err = os.path.join(savedir, "err.txt")
        command = '"%s 1>%s 2>%s"' % (command, path_log, path_err)

    eai_command += " -- /bin/bash -c %s" % command

    # Return the Borgy command in Byte format
    return r'''body'''.replace("body", eai_command)

def kill_job(api, job_id):
    """Kill a job job until it is dead."""
    job = get_job(api, job_id)

    if not job.alive:
        print('%s is already dead' % job_id)
    else:
        hu.subprocess_call("borgy kill %s" % job_id)
        print('%s CANCELLING...' % job_id)
        job = get_job(api, job_id)
        while job.state == "CANCELLING":
            time.sleep(2.0)
            job = get_job(api, job_id)

        print('%s now is dead.' % job_id)
