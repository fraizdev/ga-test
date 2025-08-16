from pathlib import Path

import pytest
from client.lock import LockClient
from client.system import windows_check
from pytest_mock import MockerFixture


@pytest.fixture
def lock_client() -> LockClient:
    return LockClient()


def test_acquire(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_lockfile = mocker.patch.object(
        LockClient, 'lockfile', new_callable=mocker.PropertyMock, return_value=Path('lockfile')
    )
    mock_open = mocker.patch('os.open', return_value=mocker.MagicMock())
    mock_close = mocker.patch('os.close')
    mock_lock = mocker.patch('msvcrt.locking' if windows_check() else 'fcntl.flock')
    mock_fchmod = mocker.patch('os.fchmod' if not windows_check() else 'builtins.id')

    with lock_client.acquire() as lock:
        assert lock.is_locked
        mock_open.assert_called_once()
        mock_lock.assert_called_once()
        if not windows_check():
            mock_fchmod.assert_called_once_with(lock_client._fd, lock_client._mode)

    mock_close.assert_called_once()
    assert not lock_client.is_locked
    assert mock_lockfile.call_count > 1


def test_acquire_permission_error(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_lockfile = mocker.patch.object(
        LockClient, 'lockfile', new_callable=mocker.PropertyMock, return_value=Path('lockfile')
    )
    mock_open = mocker.patch('os.open', side_effect=PermissionError('Permission denied'))

    acquire_lock = lock_client.acquire()
    mock_open.assert_called_once()
    assert not lock_client.is_locked
    assert isinstance(acquire_lock.lock, LockClient)
    assert mock_lockfile.call_count > 1


def test_release(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_lockfile = mocker.patch.object(
        LockClient, 'lockfile', new_callable=mocker.PropertyMock, return_value=Path('lockfile')
    )
    mock_fd = mocker.MagicMock()
    lock_client._fd = mock_fd

    mock_unlink = mocker.patch.object(Path, 'unlink', return_value=None)
    mock_fchmod = mocker.patch('os.fchmod' if not windows_check() else 'builtins.id')
    mock_lock = mocker.patch('msvcrt.locking' if windows_check() else 'fcntl.flock')
    mock_close = mocker.patch('os.close')

    lock_client.release()

    mock_lock.assert_called_once()
    if not windows_check():
        mock_fchmod.assert_called_once_with(mock_fd, lock_client._mode)
    mock_close.assert_called_once_with(mock_fd)
    mock_unlink.assert_called_once()
    assert not lock_client.is_locked
    assert mock_lockfile.call_count > 1


def test_exists_with_no_running(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_lock = mocker.patch(
        'msvcrt.locking' if windows_check() else 'fcntl.flock', side_effect=OSError('Lock error')
    )
    mock_exists = mocker.patch.object(Path, 'exists', return_value=True)
    mock_open = mocker.patch.object(Path, 'open')

    result = lock_client.exists_running

    mock_exists.assert_called_once()
    mock_open.assert_called_once()
    mock_lock.assert_called_once()
    assert result


def test_exists_with_running(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_lock = mocker.patch('msvcrt.locking' if windows_check() else 'fcntl.flock')
    mock_exists = mocker.patch.object(Path, 'exists', return_value=True)
    mock_open = mocker.patch.object(Path, 'open')

    result = lock_client.exists_running

    mock_exists.assert_called_once()
    mock_open.assert_called_once()
    mock_lock.assert_called()
    assert not result


def test_wait_no_existing(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_running = mocker.patch.object(
        LockClient, 'exists_running', new_callable=mocker.PropertyMock, return_value=False
    )

    result = lock_client.wait(timeout=1)

    mock_running.assert_called_once()
    assert result


def test_wait_with_existing(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_running = mocker.patch.object(
        LockClient,
        'exists_running',
        new_callable=mocker.PropertyMock,
        side_effect=[True, True, False],
    )

    result = lock_client.wait(timeout=2, interval=0.1)

    mock_running.assert_called()
    assert result


def test_wait_timeout(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_running = mocker.patch.object(
        LockClient,
        'exists_running',
        new_callable=mocker.PropertyMock,
        return_value=True,
    )

    result = lock_client.wait(timeout=0.3, interval=0.1)

    mock_running.assert_called()
    assert not result


def test_context_manager_usage(mocker: MockerFixture, lock_client: LockClient) -> None:
    mock_acquire = mocker.patch.object(LockClient, 'acquire')
    mock_release = mocker.patch.object(LockClient, 'release')

    with lock_client:
        mock_acquire.assert_called_once()
    mock_release.assert_called_once()
