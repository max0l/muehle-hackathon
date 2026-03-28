# openapi_client.DefaultApi

All URIs are relative to *http://172.28.40.187:40000*

Method | HTTP request | Description
------------- | ------------- | -------------
[**add_player**](DefaultApi.md#add_player) | **POST** /games/{gameId}/players | Spieler zum Spiel hinzufügen
[**create_game**](DefaultApi.md#create_game) | **POST** /games | Neues Spiel anlegen
[**get_board**](DefaultApi.md#get_board) | **GET** /games/{gameId}/board | Brett mit Feldern
[**get_current_player**](DefaultApi.md#get_current_player) | **GET** /games/{gameId}/current-player | Farbe des aktuellen Spielers
[**get_game_state**](DefaultApi.md#get_game_state) | **GET** /games/{gameId}/state | Spielphase abfragen
[**get_open_api_spec**](DefaultApi.md#get_open_api_spec) | **GET** /openapi.yaml | OpenAPI-Spezifikation (diese Datei)
[**submit_move**](DefaultApi.md#submit_move) | **POST** /games/{gameId}/moves | Zug ausführen (setzen, ziehen, entfernen)


# **add_player**
> AddPlayer200Response add_player(game_id, player_name)

Spieler zum Spiel hinzufügen

### Example


```python
import openapi_client
from openapi_client.models.add_player200_response import AddPlayer200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)
    game_id = UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d') # UUID | 
    player_name = 'player_name_example' # str | 

    try:
        # Spieler zum Spiel hinzufügen
        api_response = api_instance.add_player(game_id, player_name)
        print("The response of DefaultApi->add_player:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->add_player: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **game_id** | **UUID**|  | 
 **player_name** | **str**|  | 

### Return type

[**AddPlayer200Response**](AddPlayer200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/x-www-form-urlencoded
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Spieler hinzugefügt |  -  |
**404** | Unbekanntes oder ungültiges Spiel |  -  |
**500** | z. B. Spiel voll |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **create_game**
> CreateGame201Response create_game()

Neues Spiel anlegen

Erzeugt eine neue Partie. Mehrfaches Aufrufen legt mehrere unabhängige
Spiele an (jeweils neue UUID in der Antwort).


### Example


```python
import openapi_client
from openapi_client.models.create_game201_response import CreateGame201Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)

    try:
        # Neues Spiel anlegen
        api_response = api_instance.create_game()
        print("The response of DefaultApi->create_game:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->create_game: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

### Return type

[**CreateGame201Response**](CreateGame201Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Spiel erzeugt |  -  |
**500** | Serverfehler |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_board**
> GetBoard200Response get_board(game_id)

Brett mit Feldern

### Example


```python
import openapi_client
from openapi_client.models.get_board200_response import GetBoard200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)
    game_id = UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d') # UUID | 

    try:
        # Brett mit Feldern
        api_response = api_instance.get_board(game_id)
        print("The response of DefaultApi->get_board:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->get_board: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **game_id** | **UUID**|  | 

### Return type

[**GetBoard200Response**](GetBoard200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** |  |  -  |
**404** | Unbekanntes oder ungültiges Spiel |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_current_player**
> GetCurrentPlayer200Response get_current_player(game_id)

Farbe des aktuellen Spielers

### Example


```python
import openapi_client
from openapi_client.models.get_current_player200_response import GetCurrentPlayer200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)
    game_id = UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d') # UUID | 

    try:
        # Farbe des aktuellen Spielers
        api_response = api_instance.get_current_player(game_id)
        print("The response of DefaultApi->get_current_player:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->get_current_player: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **game_id** | **UUID**|  | 

### Return type

[**GetCurrentPlayer200Response**](GetCurrentPlayer200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** |  |  -  |
**404** | Unbekanntes oder ungültiges Spiel |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_game_state**
> GetGameState200Response get_game_state(game_id)

Spielphase abfragen

### Example


```python
import openapi_client
from openapi_client.models.get_game_state200_response import GetGameState200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)
    game_id = UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d') # UUID | 

    try:
        # Spielphase abfragen
        api_response = api_instance.get_game_state(game_id)
        print("The response of DefaultApi->get_game_state:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->get_game_state: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **game_id** | **UUID**|  | 

### Return type

[**GetGameState200Response**](GetGameState200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** |  |  -  |
**404** | Unbekanntes oder ungültiges Spiel |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_open_api_spec**
> str get_open_api_spec()

OpenAPI-Spezifikation (diese Datei)

### Example


```python
import openapi_client
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)

    try:
        # OpenAPI-Spezifikation (diese Datei)
        api_response = api_instance.get_open_api_spec()
        print("The response of DefaultApi->get_open_api_spec:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->get_open_api_spec: %s\n" % e)
```



### Parameters

This endpoint does not need any parameter.

### Return type

**str**

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/yaml

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | OpenAPI 3.0 Dokument (YAML) |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **submit_move**
> SubmitMove200Response submit_move(game_id, action, secret_code, field_index=field_index, to_field_index=to_field_index)

Zug ausführen (setzen, ziehen, entfernen)

### Example


```python
import openapi_client
from openapi_client.models.submit_move200_response import SubmitMove200Response
from openapi_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://172.28.40.187:40000
# See configuration.py for a list of all supported configuration parameters.
configuration = openapi_client.Configuration(
    host = "http://172.28.40.187:40000"
)


# Enter a context with an instance of the API client
with openapi_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = openapi_client.DefaultApi(api_client)
    game_id = UUID('38400000-8cf0-11bd-b23e-10b96e4ef00d') # UUID | 
    action = 'action_example' # str | 
    secret_code = 'secret_code_example' # str | 
    field_index = 'field_index_example' # str | Bei place/remove Quell-/Zielfeld; bei move Startfeld (optional)
    to_field_index = 'to_field_index_example' # str | Nur bei action=move (optional)

    try:
        # Zug ausführen (setzen, ziehen, entfernen)
        api_response = api_instance.submit_move(game_id, action, secret_code, field_index=field_index, to_field_index=to_field_index)
        print("The response of DefaultApi->submit_move:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->submit_move: %s\n" % e)
```



### Parameters


Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **game_id** | **UUID**|  | 
 **action** | **str**|  | 
 **secret_code** | **str**|  | 
 **field_index** | **str**| Bei place/remove Quell-/Zielfeld; bei move Startfeld | [optional] 
 **to_field_index** | **str**| Nur bei action&#x3D;move | [optional] 

### Return type

[**SubmitMove200Response**](SubmitMove200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/x-www-form-urlencoded
 - **Accept**: application/json

### HTTP response details

| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Zug akzeptiert |  -  |
**400** | Ungültige action oder fehlende Felder |  -  |
**404** | Unbekanntes oder ungültiges Spiel |  -  |
**500** | Regelverletzung o. Ä. |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

