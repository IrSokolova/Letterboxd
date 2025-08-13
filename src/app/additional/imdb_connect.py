import http.client
import random
import json
from time import sleep
import sys


def random_imdb_id():
    conn = http.client.HTTPSConnection("api.imdbapi.dev")
    while True:
        potential_id = "{:07d}".format(random.randint(1, 400000))
        url = "/titles/" + "tt" + str(potential_id)
        conn.request("GET", url)
        res = conn.getresponse()
        if res.status == 200:
            data = res.read()
            data_dict = json.loads(data.decode("utf-8"))
            if data_dict["type"] == "movie":
                conn.close()
                return "tt" + str(potential_id)
        sleep(4)


def get_rand_movie_info():
    id = random_imdb_id()
    return get_movie_info(id)

def get_movie_info(imdb_id: str):
    res_dict = {}
    conn = http.client.HTTPSConnection("api.imdbapi.dev")
    conn.request("GET", "/titles/" + imdb_id)
    res = conn.getresponse()
    data = res.read()
    data_dict = json.loads(data.decode("utf-8"))

    res_dict["imdb_id"] = imdb_id
    res_dict["name"] = data_dict["primaryTitle"]
    if "plot" in data_dict.keys():
        res_dict["description"] = data_dict["plot"]
    else:
        res_dict["description"] = None

    if "primaryImage" in data_dict.keys():
        if "url" in data_dict["primaryImage"].keys():
            res_dict["poster_url"] = data_dict["primaryImage"]["url"]
        else:
            res_dict["poster_url"] = None
    else:
        res_dict["poster_url"] = None

    res_dict["start_year"] = data_dict["startYear"]

    return res_dict