import math
import time
import boto3


AWS_REGION='us-east-1'
AWS_ACCESS_KEY=""
AWS_SECRET_ACCESS_KEY=""
INPUT_QUEUE_NAME=""
OUTPUT_QUEUE_NAME=""
AMI_ID=''
SECURITY_GROUP_ID=''

QUEUE_URL=""


user_data = '''#!/bin/bash
cd /home/ubuntu/classifier
sudo chmod -R 777 .
touch new_file.txt
echo 'new text here' >> new_file.txt
su ubuntu -c 'python3 recognition.py > execution_logs.txt'
touch after_run.txt'''

current=0
tracker=[0,0,0,0,0]
idx=-1

sqsclient = boto3.client("sqs",region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
ec2resource = boto3.resource('ec2',region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)


def get_required_instance_count():
    response=sqsclient.get_queue_attributes(
        QueueUrl=QUEUE_URL,
        AttributeNames=['ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible','ApproximateNumberOfMessagesDelayed']
    )

    queue_size=int(response['Attributes']['ApproximateNumberOfMessages']) + int(response['Attributes']['ApproximateNumberOfMessagesNotVisible'])
    print("Current queue size : "+ str(queue_size))

    required_instances_for_create=math.ceil(queue_size/2)
    required_instances_for_terminate=math.ceil(queue_size/10)

    return required_instances_for_create,required_instances_for_terminate

    
def create_apptier_instances(number):
    print("Inside create_apptier_instances()")
    i=0
    global current
    while i < number and current <= 17:
        current+=1

        instance_name = 'app-instance-' + str(current) 
        print("Creating ",instance_name)

        ec2resource.create_instances(
            ImageId=AMI_ID,
            InstanceType='t2.micro',
            UserData=user_data, 
            MinCount=1, MaxCount=1,
            SecurityGroupIds=[
                SECURITY_GROUP_ID,
            ],
            TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    {
                        'Key': 'Name',
                        'Value': instance_name
                    },
                    {
                        'Key':'Type',
                        'Value':'apptier'
                    }
                ]
            },
        ])

        i+=1

    time.sleep(30)
    
def find_instances(values):
    instances = ec2resource.instances.filter(
        Filters=[
            {
                'Name': 'instance-state-name', 
                'Values': values #['running','pending'] #['running']
            }, 
            {
                'Name': 'tag:Type',
                'Values': ['apptier']
            }
        ]
    )

    instances_count = 0
    for x in instances:
        instances_count+=1

    return instances,instances_count


def terminate_apptier_instances(number):

    print("Inside terminate_apptier_instances()")
   
    i=0

    while(i<number):
        global current

        appname="app-instance-" + str(current)

        instance_list=ec2resource.instances.filter(
            Filters=[
                {
                    'Name':'tag:Name',
                    'Values':[appname]
                },
                {
                    'Name': 'instance-state-name', 
                    'Values': ['running','pending']
                }
            ]
        )

        for each in instance_list:
            curr_instance=ec2resource.Instance(each.id)
            curr_instance.terminate()

        current-=1
        i+=1

        print("Terminated " + appname)  



(running_pending_instance_collection, no_of_running_pending_instances)=find_instances(['running','pending'])
current = no_of_running_pending_instances

while(True):

    required_instances_for_create,required_instances_for_terminate=get_required_instance_count()

    (running_pending_instance_collection, no_of_running_pending_instances)=find_instances(['running','pending'])
    
    print(current)
    if current <= 18:
        if (required_instances_for_create > no_of_running_pending_instances):
            instances_to_be_created = required_instances_for_create - no_of_running_pending_instances
            create_apptier_instances(instances_to_be_created)
            

        elif (required_instances_for_terminate < no_of_running_pending_instances):
            time.sleep(30)
            if idx==4:
                idx=-1
            idx+=1
            
            instances_to_be_terminated = abs(required_instances_for_terminate - no_of_running_pending_instances)
            tracker[idx]=instances_to_be_terminated
            print(tracker)
            if tracker.count(instances_to_be_terminated)==5:
                terminate_apptier_instances(instances_to_be_terminated)

    time.sleep(10)

