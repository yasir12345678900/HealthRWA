from datetime import datetime
import uuid

AUDIT=[]

def log(
    actor_did,
    actor_role,
    action,
    patient_did,
    consent_id,
    scope=None,
    purpose=None,
    result="SUCCESS",
    metadata=None,
    tx_hash=None,
    block_number=None
):

    AUDIT.append(
        {
            "event_id":str(uuid.uuid4()),
            "timestamp":datetime.now().isoformat(),
            "actor_did":actor_did,
            "actor_role":actor_role,
            "action":action,
            "patient_did":patient_did,
            "consent_id":consent_id,
            "scope":scope,
            "purpose":purpose,
            "result":result,
            "tx_hash":tx_hash,
            "block_number":block_number,
            "metadata":metadata
        }
    )


def get():
    return AUDIT



# from datetime import datetime
# import uuid


# AUDIT=[]

# def log(
#     actor_did,
#     actor_role,
#     action,
#     patient_did,
#     consent_id,
#     scope=None,
#     purpose=None,
#     result="SUCCESS",
#     metadata=None
# ):


#     event={
#         "event_id":str(uuid.uuid4()),
#         "timestamp":datetime.now().isoformat(),
#         "actor_did":actor_did,
#         "actor_role":actor_role,
#         "action":action,
#         "patient_did":patient_did,
#         "consent_id":consent_id,
#         "scope":scope,
#         "purpose":purpose,
#         "result":result,
#         "metadata":metadata
#     }
#     AUDIT.append(event)


    


# def get():
#     return AUDIT