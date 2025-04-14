import random
import re
import string
from django.contrib.auth import get_user_model, authenticate


def random_string_generator(size=10, chars=string.ascii_lowercase + string.digits):
    return "".join(random.choice(chars) for _ in range(size))


def generate_random_otp_code():
    code = ""
    for i in range(4):
        code += str(random.randint(0, 9))
    return code


def unique_user_id_generator(instance):
    """
    This is for a django project with a user_id field
    :param instance:
    :return:
    """

    size = random.randint(30, 45)
    user_id = random_string_generator(size=size)

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(user_id=user_id).exists()
    if qs_exists:
        return
    return user_id



def generate_email_token():
    code = ""
    for i in range(4):
        code += str(random.randint(0, 9))
    return code


def unique_ref_number_generator():
    size = random.randint(5, 15)
    ref = "#REF-" + random_string_generator(size=size, chars=string.ascii_uppercase + string.digits)
    return ref
def unique_ticket_number_generator():
    size = random.randint(5, 15)
    ref = "#TIC-" + random_string_generator(size=size, chars=string.ascii_uppercase + string.digits)

    return ref


