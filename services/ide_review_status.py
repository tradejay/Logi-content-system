"""Project collected review results onto the existing static comparison page."""
from .ide_worker_bridge import ROOT,load,save


def sync(worker_folder, task_id, state, root=ROOT):
    if state.get('status')!='collected' or state.get('result_status')!='completed':return
    worker=root/'worker-workspaces'/worker_folder
    task=load(worker/'inbox'/task_id/'task.json')
    if task.get('stage')!='feedback' or not task_id.endswith('-REVIEW'):return
    page=root/'static/experiments/naver-ide-full'/task_id[:-7]/'index.html'
    result_path=worker/'work'/task_id/'feedback/review.json'
    if not page.exists() or not result_path.exists():return
    result=load(result_path)
    if type(result.get('passed')) is not bool or not isinstance(result.get('issues'),list):raise ValueError('Invalid review result')
    target=page.parent/'review.json'
    if not target.exists() or load(target)!=result:save(target,result)
    label='독립 리뷰 통과' if result['passed'] else f"독립 리뷰 수정 필요 ({len(result['issues'])}건)"
    text=page.read_text(encoding='utf-8')
    revised=text.replace('독립 리뷰는 별도 확인',label).replace('독립 리뷰 대기',label)
    if revised!=text:page.write_text(revised,encoding='utf-8')
