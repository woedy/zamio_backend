import random
import re
import string

from django.conf import settings


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




def unique_admin_id_generator(instance):
    """
    This is for a admin_id field
    :param instance:
    :return:
    """
    size = random.randint(5, 10)
    admin_id = "AD-" + random_string_generator(size=size, chars=string.ascii_uppercase + string.digits) + "-IN"

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(admin_id=admin_id).exists()
    if qs_exists:
        return None
    return admin_id


def unique_artist_id_generator(instance):
    """
    This is for a artist_id field
    :param instance:
    :return:
    """
    size = random.randint(5, 10)
    artist_id = "AR-" + random_string_generator(size=size, chars=string.ascii_uppercase + string.digits) + "-ST"

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(artist_id=artist_id).exists()
    if qs_exists:
        return None
    return artist_id

def unique_track_id_generator(instance):
    """
    This is for a track_id field
    :param instance:
    :return:
    """
    size = random.randint(5, 10)
    track_id = "TR-" + random_string_generator(size=size, chars=string.ascii_uppercase + string.digits) + "-CK"

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(track_id=track_id).exists()
    if qs_exists:
        return None
    return track_id


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







def is_valid_email(email):
    # Regular expression pattern for basic email validation
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

    # Using re.match to check if the email matches the pattern
    if re.match(pattern, email):
        return True
    else:
        return False


def is_valid_password(password):
    # Check for at least 8 characters
    if len(password) < 8:
        return False

    # Check for at least one uppercase letter
    if not re.search(r'[A-Z]', password):
        return False

    # Check for at least one lowercase letter
    if not re.search(r'[a-z]', password):
        return False

    # Check for at least one digit
    if not re.search(r'[0-9]', password):
        return False

    # Check for at least one special character
    if not re.search(r'[-!@#\$%^&*_()-+=/.,<>?"~`£{}|:;]', password):
        return False

    return True




def unique_account_id_generator(instance):
    """
    This is for a account_id field
    :param instance:
    :return:
    """
    size = random.randint(5, 7)
    account_id = "ACC-" + random_string_generator(size=size, chars=string.ascii_uppercase + string.digits) + "-(BNK)"

    Klass = instance.__class__
    qs_exists = Klass.objects.filter(account_id=account_id).exists()
    if qs_exists:
        return None
    return account_id