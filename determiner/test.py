import io
import json

def dict_to_json_buffer(dict_):
    s_buffer = io.StringIO()
    json.dump(dict_, s_buffer)
    print(s_buffer.getvalue())
    b_buffer = io.BytesIO(s_buffer.getvalue().encode('utf8'))

    return b_buffer

d = {
    "a":1
}

buffer = dict_to_json_buffer(d)

buffer_len = buffer.getbuffer().nbytes
buffer.seek(0)

print(buffer_len)