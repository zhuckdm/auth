from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html
)
from fastapi.staticfiles import StaticFiles
from starlette import status
from starlette.responses import FileResponse, Response

from src.app.services import *
from src.app.exceptions_services import *


users, admin, auth_handler, messenger = get_app_src(get_app_config())
app = FastAPI(docs_url=None, redoc_url=None)
app.mount("/src/static", StaticFiles(directory="src/static"), name="static")


@app.get('/refresh-token')
def get_refresh_token(mail: str, code=None):
    """
    Получить refresh token по указанной почте. Если к этой почте уже прикреплен валидный, актуальный токен
    на почту придет код подтверждения, который нужно ввести через этот же метод для сброса текущего refresh token
    и получения нового
    """
    mail = mail.lower()
    get_401_if_invalid_mail(mail)
    auth_handler.get_500_if_db_is_not_connected()
    if code is None:
        need_confirmation_code = auth_handler.is_valid_rt_for_mail(mail)

        if need_confirmation_code:
            new_confirmation_code = auth_handler.get_new_code_for_mail(mail)
            messenger.send_code_for_receipt_rt(mail, new_confirmation_code)
        else:
            new_rt_hash = auth_handler.get_new_rt_hash(mail)
            add_user_if_it_is_not_in_db(mail, users)
            messenger.send_rt_hash(mail, new_rt_hash)

        result = {'need_confirmation_code': need_confirmation_code}
    else:
        auth_handler.get_401_if_there_is_no_code_for_this_mail(mail)
        auth_handler.get_401_and_reset_code_if_it_is_invalid(mail, code)

        new_rt_hash = auth_handler.get_new_rt_hash(mail)
        messenger.send_rt_hash(mail, new_rt_hash)
        result = Response(status_code=status.HTTP_204_NO_CONTENT)
    return result


@app.get('/access-token')
def get_access_token(refresh_token: str):
    """
    На основе refresh token получить новый access token,
    в случае невалидного refresh token вернется ошибка 401
    """
    auth_handler.get_500_if_db_is_not_connected()
    new_access_token = auth_handler.refresh_at(refresh_token)
    return {'access_token': new_access_token}


@app.get('/check-access-token')
def check_access_token(access_token: str):
    """Вывести информацию access token или ошибку 401, если токен невалидный/устаревший"""
    auth_handler.get_500_if_db_is_not_connected()
    return auth_handler.decode_at(access_token)


@app.get('/user-data')
def get_user_data(mail: str):
    """Получает информацию о пользователе по его почте"""
    mail = mail.lower()
    get_401_if_invalid_mail(mail)
    get_500_if_users_db_is_not_connected(users)
    get_404_if_unregistered_mail(mail, users)
    return get_user_data_by_mail(users, mail)


@app.put('/user-data')
def put_user_data(access_token: str, mail: str, data: str):
    """
    По access token администратора, обновить данные пользователя
    по указанной электронной почте на передаваемые данные в формате JSON
    """
    mail = mail.lower()
    get_500_if_users_db_is_not_connected(users)
    get_500_if_admin_db_is_not_connected(admin)
    get_403_if_is_not_admin(admin, auth_handler.get_mail_by_at(access_token))
    get_400_if_invalid_mail(mail)
    get_404_if_unregistered_mail(mail, users)
    data_for_update = get_data_for_update_or_400(data)
    update_user(mail, data_for_update, users)
    if 'mail' in data_for_update:
        mail = data_for_update['mail']
    return get_user_data_by_mail(users, mail)


# -----------------------------Служебный код---------------------------------------------
@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    file_name = "logo_main.png"
    file_path = f"src/static/{file_name}"
    return FileResponse(path=file_path, headers={"Content-Disposition": f"attachment; filename={file_name}"})


# ----------------------Код для работы документации--------------------------------------
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="/src/static/swagger-ui-bundle.js",
        swagger_css_url="/src/static/swagger-ui.css",
        swagger_favicon_url="/src/static/logo_swagger.png"
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="/src/static/redoc.standalone.js",
        redoc_favicon_url="/src/static/logo_redoc.png"
    )
