# Authentication

Http session authentication is not strictly part of DICOM server interaction. However, it is a practical issue that
will pop up in real-world situations. Every vendor, model, server installation will have its own authentication
mechanism. As such it is impossible to provide a generic solution. Dicomtrolley ships with authentication adapters for
the `Vitrea Connection 8.2.0.1` system that it was developed on.

## Vitrea Auth
There is a custom [requests authentication](https://docs.python-requests.org/en/latest/user/advanced/#custom-authentication)
class for Vitrea Connection:
```python
session = requests.Session()
session.auth = VitreaAuth(
    login_url="https://server/login",
    user="user",
    password="password",
    realm="realm",
)

# then just use the session
searcher=Mint(session, "https://server/mint")
```
One advantage of using an `requests.auth.AuthBase` class is that login is automatically retried should authentication
time out or be disrupted for other reasons.

## Custom Auth
The only thing dicomtrolley needs is an authenticated `requests.Session` instance:
```python
session = requests.Session()

# do whatever you need to authenticate
session.post("https://server/login", 
             headers={"user":"a_user", 
                      "password":"secret"})

# use session in trolley, searcher and downloader creation
trolley=Trolley(searcher=Mint(session, "https://server/mint"),
                downloader=WadoRS(session, "https://server/wadors"))
```
