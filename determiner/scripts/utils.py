import string
import random

def random_id(length):
    string_pool = string.ascii_uppercase + string.digits
    result = ""

    for i in range(length) :
        result += random.choice(string_pool)
    
    return result

if __name__ == "__main__":
    print(random_id(10))