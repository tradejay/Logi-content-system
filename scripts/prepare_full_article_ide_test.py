"""Create a content-only whole-article test task; bookkeeping is host-owned."""
from services.ide_edit_task import prepare

if __name__ == '__main__':
    print(prepare())
