import pytest
from client.socket import SocketClient
from client.system import windows_check
from pytest_mock import MockerFixture


@pytest.fixture
def socket_client() -> SocketClient:
    return SocketClient(__name__)


def test_connect(mocker: MockerFixture, socket_client: SocketClient) -> None:
    if windows_check():
        mock_socket = mocker.patch('builtins.open', return_value=mocker.MagicMock())
    else:
        mock_socket = mocker.patch('socket.socket', return_value=mocker.MagicMock())

    with socket_client.connect() as socket:
        mock_socket.assert_called_once()
        assert socket.is_connect
        if not windows_check():
            mock_socket().connect.assert_called_once()

    mock_socket().close.assert_called_once()
    assert not socket_client.is_connect


def test_connect_permission_error(mocker: MockerFixture, socket_client: SocketClient) -> None:
    mocker.patch('builtins.open', side_effect=FileNotFoundError('File not exist'))

    connect_socket = socket_client.connect()

    assert not socket_client.is_connect
    assert isinstance(connect_socket.socket, SocketClient)


def test_disconnect(mocker: MockerFixture, socket_client: SocketClient) -> None:
    mock_pipe = mocker.MagicMock()
    socket_client._pipe = mock_pipe

    socket_client.disconnect()

    mock_pipe.close.assert_called_once()
    assert not socket_client.is_connect


def test_send(mocker: MockerFixture, socket_client: SocketClient) -> None:
    mock_pipe = mocker.MagicMock()
    socket_client._pipe = mock_pipe

    mock_data = mocker.MagicMock()
    socket_client.send(mock_data)

    if windows_check():
        mock_pipe.write.assert_called_once_with(mock_data.encode('utf-8'))
    else:
        mock_pipe.send.assert_called_once_with(mock_data.encode('utf-8'))


def test_context_manager_usage(mocker: MockerFixture, socket_client: SocketClient) -> None:
    mock_connect = mocker.patch.object(SocketClient, 'connect')
    mock_disconnect = mocker.patch.object(SocketClient, 'disconnect')

    with socket_client:
        mock_connect.assert_called_once()
    mock_disconnect.assert_called_once()
