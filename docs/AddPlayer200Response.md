# AddPlayer200Response


## Properties

Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**message** | **str** |  | [optional] 
**secret** | **str** | Geheimcode für Züge | [optional] 

## Example

```python
from openapi_client.models.add_player200_response import AddPlayer200Response

# TODO update the JSON string below
json = "{}"
# create an instance of AddPlayer200Response from a JSON string
add_player200_response_instance = AddPlayer200Response.from_json(json)
# print the JSON string representation of the object
print(AddPlayer200Response.to_json())

# convert the object into a dict
add_player200_response_dict = add_player200_response_instance.to_dict()
# create an instance of AddPlayer200Response from a dict
add_player200_response_from_dict = AddPlayer200Response.from_dict(add_player200_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)


