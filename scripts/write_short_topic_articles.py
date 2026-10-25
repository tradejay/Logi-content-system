"""Render hand-authored short examples for the existing 20 topic plans."""
import json
from pathlib import Path
from html import escape

ROOT=Path(__file__).resolve().parents[1]
plans=json.loads((ROOT/'content-system/00_system/templates/articles/article-plans.json').read_text(encoding='utf-8'))['plans']
blog={'meetup':'https://blog.naver.com/oceantech01/224320922118','mini':'https://blog.naver.com/oceantech01/224283221586','bar':'https://blog.naver.com/oceantech01/224277890299','mic':'https://blog.naver.com/oceantech01/224323353470','tap':'https://blog.naver.com/oceantech01/224324760360','tapip':'https://blog.naver.com/oceantech01/224324825914'}
names={'meetup':'MeetUp 2','mini':'Rally Bar Mini','bar':'Rally Bar','mic':'Rally Mic Pod','tap':'Tap','tapip':'Tap IP'}
sources={
 'meetup':('https://www.logitech.com/content/dam/logitech/en_us/video-collaboration/pdf/meetup2-datasheet.pdf','MeetUp 2 공식 데이터시트'),
 'setup':('https://hub.sync.logitech.com/meetup2/post/1-meetup-2---setup-rkI2gIxcHAaIUnn','MeetUp 2 공식 설치 안내'),
 'mini':('https://www.logitech.com/en-us/business/shop/p/rallybarmini','Rally Bar Mini 공식 제품 안내'),
 'bar':('https://www.logitech.com/en-us/products/video-conferencing/room-solutions/rallybar.html','Rally Bar 공식 제품 안내'),
 'mic':('https://hub.sync.logitech.com/rally/post/mic-pod-placement-and-mounting-guides-iq8S2UeBlaVEEyg','공식 마이크 배치·설치 가이드'),
 'view':('https://hub.sync.logitech.com/collabosguides/post/3-4-rightsight-2-speaker-view-group-view-PXdfb8qcHkzCMwb','RightSight 2 공식 모드 안내'),
 'tap':('https://hub.sync.logitech.com/tapcat5e/post/how-to-set-up-tap-with-bundled-pc-KbHhZGDtzvdlLZa','Tap 공식 설치 안내'),
 'tapip':('https://hub.sync.logitech.com/tapip/post/how-do-i-connect-logitech-tap-ip-QReGK1OkzmqzeNY','Tap IP 공식 연결 안내'),
 'compat':('https://hub.sync.logitech.com/tapip/post/logitech-tap-family-compatibility-information-lDlBFLSxeFMJU0u','Tap·Tap IP 공식 호환 안내'),
 'modes':('https://hub.sync.logitech.com/learn/post/exploring-the-three-modes-of-logitech-rally-bars-etpo2ths3sqRkQc','Rally Bar 계열 공식 운영 모드 안내'),
 'echo':('https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0061720','Zoom 공식 에코 점검 안내'),
 'audio':('https://hub.sync.logitech.com/collabosguides/post/when-i-connect-rally-bar-or-rally-bar-mini-the-sound-comes-out-of-the-3vfLOvdxYVcAuqC','Rally Bar 계열 USB 모드 오디오 선택 안내'),
 'video':('https://hub.sync.logitech.com/rallybarmini/post/my-rally-bar-rally-bar-mini-video-doesn-t-look-right-GLGLGZc0APUQGpC','Rally Bar 계열 USB 모드 카메라 선택 안내')
}
# Exact URL case retained from the vendor result.
sources['tap']=('https://hub.sync.logitech.com/tapcat5e/post/how-to-set-up-tap-with-bundled-pc-KbHhZGDtzvdlLZa','Tap 공식 설치 안내')
images={'meetup':'https://drive.google.com/thumbnail?id=1-5pI7OBu-R_z4lbtFpJCT-GazF-tchzH&sz=w1000','mini':'https://drive.google.com/thumbnail?id=1OdGNn4P03EVikLNL0faIh21UfZEqxWm4&sz=w1000','bar':'article-sample-media/rally-bar.png','mic':'article-sample-media/mic-pod.png','group':'article-sample-media/official-group.png','speaker':'article-sample-media/official-speaker.png'}
def p(text):return '<p>'+text+'</p>'
def links(*keys):return ''.join(f'<a class="link-card" href="{blog[k]}" target="_blank" rel="noopener noreferrer">👉 관련 제품 소개: {names[k]}</a>' for k in keys)
def refs(*keys):return ''.join(f'<a class="source" href="{escape(sources[k][0],quote=True)}" target="_blank" rel="noopener noreferrer">근거: {sources[k][1]}</a>' for k in keys)
def photo(k):return f'<figure class="media"><img src="{escape(images[k],quote=True)}" alt="{names.get(k,k)}" loading="lazy"><figcaption>{names.get(k,k)} · 기존 제품·동작 자료</figcaption></figure>'
def diagram(*labels):return '<div class="diagram">'+' → '.join('<span>'+escape(x)+'</span>' for x in labels)+'</div>'
def sec(role,title,text,extra='',recommend=False):return [role,title,p(text)+extra,recommend]
def rec(title,text,*products):return sec('추천·조건',title,text,photo(products[0])+links(*products),True)
drafts=[]
def add(intro,sections,closing):drafts.append({'intro':intro,'sections':sections,'closing':closing})

add('TV는 켜졌는데 회의 화면이 안 보이거나 소리가 노트북에서만 나오나요? 화면 연결과 회의용 오디오를 나눠 확인하면 점검 순서가 단순해집니다.',[
 sec('증상','1. 화면과 소리를 따로 확인하세요','TV에 화면이 없는지, 화면은 있는데 소리만 다른 곳에서 나오는지 구분합니다. 두 증상을 한 번에 해결하려고 설정을 여러 개 바꾸면 무엇이 효과가 있었는지 알기 어렵습니다.'),
 sec('점검','2. TV 입력과 오디오 장치를 확인합니다','TV 입력이 연결한 단자와 맞는지 보고, 노트북의 표시 모드를 확인하세요. Rally Bar 계열을 USB 모드로 쓴다면 호스트 컴퓨터에서 마이크와 스피커가 해당 장치로 선택됐는지도 점검합니다.',refs('audio')+diagram('TV 입력','노트북 화면','마이크·스피커 선택')),
 rec('3. 연결을 정리하려면 MeetUp 2를 검토하세요','영상·음성 장비를 함께 정리할 소회의실에는 <strong>MeetUp 2</strong>를 추천 후보로 잡을 수 있습니다. TV 출력 문제를 자동으로 해결하는 제품은 아니므로, 먼저 기존 연결을 점검하고 공식 BYOD 구성에 맞는 케이블을 선택하세요.','meetup'),
 sec('정상 확인','4. 영상과 통화 음성을 다시 확인합니다','TV에서 회의 화면이 보이는지, 상대방 목소리가 원하는 장치로 나오는지 따로 확인합니다. 문제가 남으면 사용 단자·케이블·선택 장치를 기록하세요.',refs('setup'))
],'화면 연결과 오디오 선택을 나누면 원인을 좁히기 쉽습니다. 장비 보완은 점검 뒤에 판단하고, 조치 후에는 실제 회의 앱에서 다시 확인해 보세요.')

add('회의를 켜자 삐 소리가 나거나 내 목소리가 돌아오나요? 먼저 소리의 종류와 같은 공간의 중복 오디오 접속을 구분해 보겠습니다.',[
 sec('증상','1. 삐 소리와 메아리를 구분합니다','높은 삐 소리와 잠시 뒤 되돌아오는 목소리는 점검할 상황이 다릅니다. 어떤 장치가 켜져 있을 때 생기는지부터 기록해 보세요.'),
 sec('점검·조치','2. 같은 방의 중복 오디오 접속부터 줄입니다','Zoom 회의에 같은 방의 여러 컴퓨터가 오디오로 접속했다면 다른 장치의 컴퓨터 오디오 연결을 해제해 확인하세요. 음소거만으로 끝내기보다 스피커가 켜진 장치도 살펴봅니다.',refs('echo')+diagram('중복 접속 확인','오디오 연결 정리','재통화')),
 rec('3. 영상·음성을 한곳에 모을 때 MeetUp 2를 검토합니다','소회의실의 여러 마이크·스피커를 정리하려면 <strong>MeetUp 2</strong> 같은 올인원 장비를 추천 후보로 검토할 수 있습니다. 장비 교체만으로 모든 울림이 없어지는 것은 아니며, 배치와 실내 반향도 함께 확인해야 합니다.','meetup'),
 sec('확인','4. 같은 조건에서 다시 통화합니다','앞자리와 끝자리에서 번갈아 말하며 증상이 남는지 확인하세요. 제품의 오디오 처리와 중복 접속 점검은 서로 다른 역할입니다.',refs('meetup'))
],'중복 오디오 경로를 먼저 정리하고 남는 문제를 확인하세요. 장비는 그다음 환경에 맞춰 검토하는 것이 좋습니다.')

add('견적서에 장비와 부속이 많으면 무엇이 꼭 필요한지 헷갈립니다. 장비 이름보다 회의실에서 맡을 역할부터 나눠보세요.',[
 sec('요구 조건','1. 회의 방식부터 정합니다','개인 노트북으로 회의할지, 회의실 전용 시스템으로 운영할지 먼저 정하세요. 같은 공간이라도 실행 방식에 따라 필요한 구성과 관리 항목이 달라집니다.'),
 sec('장비 역할','2. 구매·재사용·추가 옵션을 나눕니다','화면은 기존 TV로, 회의 실행은 노트북으로 맡길 수 있는지 확인합니다. 카메라·마이크·스피커와 설치 부속은 각각 필요한 이유가 견적에 적혀 있어야 합니다.',diagram('기존 장비','필수 역할','조건부 부속')),
 rec('3. 소회의실 BYOD라면 MeetUp 2부터 구성합니다','기존 TV와 노트북을 활용할 소회의실에는 <strong>MeetUp 2 중심 구성</strong>을 추천 후보로 잡아보세요. 전용 룸 운영을 원하면 Rally Bar Mini 등으로 별도 구성하며, 두 방식의 견적을 같은 항목으로 비교합니다.','meetup','mini'),
 sec('도입 판단','4. 총비용과 지원 범위를 확인합니다','케이블·마운트·설치·플랫폼 라이선스가 포함되는지 구분합니다. 공간 도면과 단자 사진을 전달하면 불필요한 옵션을 줄이는 데 도움이 됩니다.',refs('setup','modes'))
],'견적은 장비 목록보다 역할과 운영 방식이 먼저입니다. 필요한 이유가 명확한 구성부터 비교해 보세요.')

add('좁은 방에서 테이블 양끝 사람이 화면 밖으로 잘리나요? 제품을 고르기 전에 카메라 거리와 실제 좌석을 함께 확인해 보겠습니다.',[
 sec('문제','1. 가장 가까운 양끝 자리를 봅니다','정면 가운데 자리만 확인하면 양끝 문제를 놓칠 수 있습니다. 평소 앉는 자리 그대로 화면을 확인하고, 얼굴이 잘리는 위치를 표시해 보세요.'),
 sec('선택 기준','2. 화각과 프레이밍은 구분합니다','렌즈가 담는 범위와 그 안에서 화면을 조정하는 기능은 다릅니다. MeetUp 2의 공식 화각은 대각 120°, 수평 113°로, 두 수치를 같은 의미로 쓰면 안 됩니다.',refs('meetup')+diagram('카메라 위치·거리','양끝 좌석','실제 화면 확인')),
 rec('3. 소회의실 BYOD에는 MeetUp 2를 추천 후보로 잡습니다','노트북을 연결하는 소회의실이라면 <strong>MeetUp 2</strong>를 검토하세요. 넓은 화각이 있어도 모든 좌석이 항상 담기는 것은 아니므로 설치 위치와 좌석을 함께 시험해야 합니다.','meetup'),
 sec('설치 확인','4. 같은 좌석으로 도입 전 확인합니다','양끝 참석자가 보이는지, 화면 조정 후 원하는 구도가 유지되는지 확인합니다. 얼굴뿐 아니라 목소리도 실제 통화로 함께 점검하세요.')
],'카메라 수치 하나보다 실제 좌석 화면이 선택 기준입니다. 양끝 자리부터 확인하면 필요한 장비를 더 쉽게 좁힐 수 있습니다.')

add('끝자리 목소리가 작다고 마이크를 아무거나 더해도 될까요? 독립 스피커폰과 기존 시스템의 확장 마이크는 맡는 역할이 다릅니다.',[
 sec('선택 고민','1. 새 음성 장치가 필요한지, 기존 장비 확장인지 봅니다','노트북에 연결해 쓸 독립 음성 장치를 찾는 상황과 이미 있는 회의실 시스템의 수음 범위를 넓히는 상황은 구분해야 합니다.'),
 sec('비교 기준','2. 역할과 호환성이 먼저입니다','스피커폰은 마이크와 스피커 역할을 함께 맡는 범주입니다. Rally Mic Pod는 호환되는 회의실 시스템의 확장 마이크이므로 독립 USB 스피커폰처럼 연결하는 장비가 아닙니다.',refs('mic','mini')),
 rec('3. Rally Bar 계열을 쓰고 있다면 Rally Mic Pod를 검토합니다','기존 <strong>Rally Bar·Rally Bar Mini</strong>에서 특정 자리의 수음을 보완하려면 <strong>Rally Mic Pod</strong>를 추천 후보로 잡으세요. 연결 가능한 수량과 배치 조건을 먼저 확인합니다.','mic'),
 sec('상황별 판단','4. 영상까지 새로 구성할 때는 별도로 봅니다','카메라와 음성 장비를 함께 새로 마련할 소회의실이라면 MeetUp 2 같은 올인원 구성을 비교할 수 있습니다. 마이크 단품과 전체 시스템 가격을 같은 조건 없이 비교하지 마세요.',links('meetup')+refs('meetup'))
],'먼저 독립 사용과 기존 시스템 확장을 구분하세요. 그다음 같은 좌석에서 목소리 전달을 확인하면 비교 기준이 명확해집니다.')

add('소회의실에서 얼굴이 작게 보이고 목소리는 노트북에만 의존하나요? 영상과 음성을 함께 맡길 장비로 MeetUp 2를 검토해 보겠습니다.',[
 sec('불편','1. 얼굴과 목소리를 함께 확인해야 합니다','좋은 화면만으로 회의가 편해지지는 않습니다. 실제 좌석에서 얼굴이 보이는지, 상대방이 발언을 되묻는지도 같이 살펴보세요.'),
 sec('제품 소개','2. MeetUp 2는 소회의실용 올인원 USB 장비입니다','카메라·마이크·스피커가 한 장비에 들어 있으며, 노트북 BYOD나 회의실 PC와 함께 사용할 수 있습니다.',photo('meetup')+links('meetup')+refs('meetup','setup')),
 sec('사용 모습','3. 회의 앱에서 영상·음성 장치를 선택합니다','노트북에 연결한 뒤 카메라·마이크·스피커 선택을 확인합니다. TV 화면 연결까지 포함한 구성은 공식 설치도에 맞춰 준비하세요.',diagram('노트북 회의 앱','MeetUp 2 영상·음성')),
 rec('4. 기존 TV를 활용할 소회의실에 추천합니다','기존 TV를 두고 노트북으로 회의하는 환경에는 <strong>MeetUp 2</strong>를 추천 후보로 검토할 수 있습니다. 가장 가까운 좌석과 끝자리에서 실제 영상·음성을 시험한 뒤 결정하세요.','meetup')
],'영상·음성을 함께 정리하려면 MeetUp 2를 후보로 잡고, 실제 좌석과 연결 조건을 확인해 보세요.')

add('회의실 앞쪽은 잘 보이는데 뒤쪽 참석자의 표정과 발언은 놓치나요? 공간과 운영 방식에 맞춰 Rally Bar의 역할을 살펴봅니다.',[
 sec('문제','1. 멀리 앉은 자리까지 확인합니다','카메라 가까운 자리만으로 전체 회의실을 평가하기 어렵습니다. 뒤쪽 얼굴이 필요한 크기로 보이는지, 발언이 전달되는지 확인하세요.'),
 sec('제품 소개','2. Rally Bar는 중형~대형 공간용 비디오 바입니다','카메라·마이크·스피커를 통합한 제품으로, USB·BYOD·어플라이언스 운영 방식을 지원합니다. 사용할 플랫폼과 운영 방식부터 정해야 합니다.',photo('bar')+links('bar')+refs('bar','modes')),
 sec('적용 방식','3. 회의 실행 위치를 정합니다','노트북이나 회의실 PC에서 앱을 실행할지, 지원되는 룸 앱을 장비에서 운영할지 결정하세요. 전용 룸 구성에서는 조작 장치와 계정 조건도 확인합니다.',diagram('운영 방식','영상·음성','조작·관리')),
 rec('4. 중형 이상 공간의 후보로 추천합니다','<strong>Rally Bar</strong>를 후보로 잡되 방 크기만으로 확정하지 마세요. 끝자리 수음이 부족하면 호환되는 Rally Mic Pod의 필요성과 배치를 함께 검토합니다.','bar','mic')
],'Rally Bar 선택은 공간과 운영 방식이 함께 결정합니다. 뒤쪽 좌석까지 확인한 뒤 필요한 확장만 더해보세요.')

add('회의 시작마다 장치와 메뉴를 찾아다니나요? 회의 실행 장치와 테이블 위 조작 장치의 역할을 나눠보면 Tap 선택이 쉬워집니다.',[
 sec('반복 조작','1. 어디에서 회의를 시작하는지 봅니다','개인 노트북에서 시작하는지, 회의실 전용 시스템의 예약 회의에 들어가는지 구분하세요. 터치 컨트롤러는 카메라나 마이크를 대신하는 장비가 아닙니다.'),
 sec('제품 비교','2. Tap과 Tap IP는 연결 방식이 다릅니다','Tap은 호환되는 회의실 구성에서 USB 연결을 사용하는 컨트롤러이며, Tap IP는 네트워크 연결형입니다. Tap IP의 전원에는 PoE 조건이 필요합니다.',links('tap','tapip')+refs('tap','tapip')+diagram('회의실 실행 장치','Tap / Tap IP 조작')),
 sec('지원 조건','3. 플랫폼과 연결 방식을 먼저 맞춥니다','제품 이름만 보고 고르지 말고 사용 플랫폼·룸 시스템의 공식 호환 목록을 확인하세요. PoE와 네트워크, USB 배선 요구를 서로 구분합니다.',refs('compat')),
 sec('추천','4. 호환되는 룸 시스템에 맞춰 추천합니다','네트워크형 조작과 PoE 환경을 갖춘 호환 룸에는 <strong>Tap IP</strong>, USB 컨트롤러를 요구하는 구성에는 <strong>Tap</strong>을 추천 후보로 잡으세요. 카메라·음성 장비와 함께 전체 구성을 확인해야 합니다.',diagram('지원 플랫폼 확인','연결·전원 준비','조작 시험'),True)
],'컨트롤러는 운영 방식과 호환성에 맞춰 고르는 장비입니다. 기존 룸 구성 정보를 준비하면 선택을 좁힐 수 있습니다.')

add('회의실 끝자리 발언만 잘 전달되지 않나요? 기존 장비를 모두 바꾸기 전에 Rally Mic Pod로 보완할 수 있는지 살펴보겠습니다.',[
 sec('부족 위치','1. 문제가 생기는 자리를 표시합니다','전체 음성이 작은지, 특정 자리만 잘 안 들리는지 확인합니다. 같은 문장을 자리별로 말해 상대방에게 확인받으면 차이가 드러납니다.'),
 sec('제품 역할','2. Rally Mic Pod는 호환 시스템의 확장 마이크입니다','Rally Bar 계열 등 호환 장비의 수음을 보완하는 마이크입니다. 아무 노트북에 독립 USB 마이크처럼 연결하는 제품으로 이해하면 안 됩니다.',photo('mic')+links('mic')+refs('mic','mini')),
 sec('배치·설치','3. 필요한 위치에 공식 규격으로 연결합니다','수음이 부족한 위치와 배선 경로를 함께 검토하세요. 지원 수량, 케이블과 허브 조건은 사용하는 시스템의 공식 안내를 따릅니다.',diagram('부족 좌석','마이크 위치','지원 연결 경로')),
 rec('4. 기존 Rally Bar 계열 수음 보완에 추천합니다','설정·배치를 점검한 뒤에도 특정 자리의 음성이 부족하다면 <strong>Rally Mic Pod</strong>를 추천 후보로 검토하세요. 설치 후에는 같은 자리에서 다시 통화해 효과를 확인합니다.','mic')
],'마이크를 늘리는 것보다 필요한 위치를 찾는 것이 먼저입니다. 호환 조건과 자리별 통화 확인까지 함께 계획하세요.')

add('Rally Bar와 Mini 중 무엇을 고를지 사양표만으로 고민되나요? 실제 회의실에서 해결할 불편을 기준으로 두 후보를 비교해 보겠습니다.',[
 sec('선택 고민','1. 가까운 자리와 먼 자리를 함께 봅니다','카메라 앞쪽에 넓게 앉는 방과 뒤로 길게 앉는 방은 요구가 다릅니다. 실제 좌석 배치를 정한 상태에서 비교하세요.'),
 sec('대상 소개','2. 공식 대상 공간은 겹치는 구간도 있습니다','Mini는 소형~중형, Rally Bar는 중형~대형 공간을 대상으로 소개됩니다. 중형 회의실이라면 이름보다 실제 영상·음성 조건이 중요합니다.',photo('mini')+links('mini','bar')+refs('mini','bar')),
 sec('공통 비교','3. 화면·음성·운영을 같은 기준으로 확인합니다','같은 좌석에서 원하는 화면이 나오는지, 끝자리 목소리가 전달되는지 비교하세요. 사용 플랫폼과 확장 마이크 필요 여부도 함께 봅니다.',diagram('같은 좌석','같은 회의 앱','화면·음성 비교')),
 rec('4. 공간별 후보를 정하고 실제로 비교합니다','소형~중형 공간은 <strong>Rally Bar Mini</strong>, 중형~대형 공간은 <strong>Rally Bar</strong>부터 추천 후보로 검토하세요. 대상이 겹치는 공간은 데모 결과와 운영 조건으로 결정하는 것이 좋습니다.','mini','bar')
],'방 크기는 출발점이고 실제 화면·음성이 결정 기준입니다. 같은 조건으로 두 후보를 확인해 보세요.')

add('소회의실 후보로 MeetUp 2와 Rally Bar Mini가 함께 보이나요? 먼저 회의를 누가, 어디에서 실행할지 정하면 비교가 쉬워집니다.',[
 sec('선택 고민','1. 개인 노트북 중심인지 전용 룸인지 정합니다','매번 노트북을 연결하는 회의와 회의실 자체에서 시작하는 회의는 준비 과정이 다릅니다. 운영 요구를 정하지 않으면 제품 기능만 비교하게 됩니다.'),
 sec('역할 비교','2. 회의 실행 방식을 나눠 봅니다','MeetUp 2는 USB·BYOD 또는 회의실 PC와 함께 쓰는 장비입니다. Rally Bar Mini는 지원되는 룸 앱을 운영하는 어플라이언스 구성도 검토할 수 있습니다.',links('meetup','mini')+refs('setup','modes')+diagram('노트북·회의실 PC','또는 전용 룸 운영')),
 sec('사용 조건','3. 연결·조작·관리를 함께 비교합니다','기존 TV·노트북을 활용할지, 컨트롤러와 룸 계정을 마련할지 구분하세요. 두 제품 모두 실제 좌석에서 영상·음성을 확인해야 합니다.'),
 rec('4. 운영 목적에 맞춰 추천합니다','노트북 중심 소회의실은 <strong>MeetUp 2</strong>, 호환되는 전용 룸 운영을 원하면 <strong>Rally Bar Mini</strong>를 후보로 추천합니다. 플랫폼 지원과 전체 구성 비용을 함께 확인하세요.','meetup','mini')
],'두 제품의 선택은 기능 개수보다 운영 방식에서 시작합니다. 필요한 연결과 조작 흐름을 먼저 정해보세요.')

add('개인 노트북을 연결할까요, 회의실 전용 시스템을 만들까요? 회의 시작과 관리 방식의 차이부터 비교해 보겠습니다.',[
 sec('운영 고민','1. 매번 연결하는 과정이 필요한지 봅니다','BYOD는 개인 노트북의 회의 앱을 사용합니다. 전용 룸은 회의실에 마련한 시스템으로 운영하므로 계정과 관리 역할도 함께 고려해야 합니다.'),
 sec('공통 기준','2. 시작·관리·외부 회의를 비교합니다','직원이 회의를 시작하는 과정, 장비 업데이트 담당자, 외부 회의 참여 요구를 같은 기준으로 정리하세요. 어느 방식이 항상 더 낫다고 단정하기 어렵습니다.',diagram('회의 시작','관리 담당','외부 회의 요구')),
 rec('3. BYOD는 MeetUp 2, 전용 룸은 Mini 구성을 검토합니다','소회의실에서 노트북을 활용하려면 <strong>MeetUp 2</strong>, 지원되는 전용 룸 운영에는 <strong>Rally Bar Mini와 호환 컨트롤러</strong>를 추천 후보로 잡을 수 있습니다. Tap IP를 더할 때는 플랫폼·네트워크·PoE 조건을 확인하세요.','meetup','mini','tapip'),
 sec('도입 판단','4. 장비 외 계정·라이선스·운영도 포함합니다','케이블 연결만 비교하지 말고 전체 비용과 관리 책임을 나눠보세요. 전용 룸에서 BYOD를 병행할 계획이라면 지원 구성도 별도로 확인합니다.',refs('setup','modes','compat'))
],'편한 회의 시작 방식과 관리 가능한 구성을 함께 선택하세요. 두 방식의 전체 운영 조건을 비교하면 방향이 분명해집니다.')

add('중형 회의실에서 뒤쪽 얼굴은 작고 끝자리 발언은 놓치나요? 영상과 음성 문제를 분리해 필요한 구성을 정리해 보겠습니다.',[
 sec('환경','1. 영상과 음성이 부족한 위치를 나눕니다','얼굴이 작게 보이는 자리와 목소리가 작게 들리는 자리가 같지 않을 수 있습니다. 좌석 배치도에 각각 표시해 보세요.'),
 sec('역할','2. 카메라 구도와 수음 위치를 함께 설계합니다','영상은 필요한 참석자를 담는 구도로, 음성은 실제 발언 위치로 확인합니다. 기본 장비 하나로 충분한지 먼저 시험한 뒤 확장을 판단하세요.',diagram('영상 부족 위치','음성 부족 위치','구성 검토')),
 rec('3. Rally Bar와 필요 시 Rally Mic Pod를 추천합니다','<strong>Rally Bar</strong>를 기본 후보로 잡고, 수음이 부족한 자리에 <strong>Rally Mic Pod</strong>를 추가할지 검토하세요. 중형이라는 이름만으로 확장을 필수로 정하지는 않습니다.','bar','mic'),
 sec('도입 확인','4. 운영 모드와 설치 조건을 맞춥니다','노트북·회의실 PC·전용 룸 중 실행 방식을 정하고, 배선과 마이크 호환 조건을 확인하세요. 도입 전에는 실제 좌석을 모두 사용하는 통화를 해보는 것이 좋습니다.',refs('bar','mic','modes'))
],'영상과 음성의 부족 위치를 따로 찾으면 필요한 보완이 명확해집니다. 실제 좌석 확인 후 필요한 부속만 더해보세요.')

add('Zoom 회의마다 장치를 연결하고 메뉴를 찾느라 시작이 늦어지나요? 노트북 Zoom과 Zoom Rooms를 먼저 구분해 보겠습니다.',[
 sec('시작 과정','1. 어디에서 Zoom을 실행하나요?','개인 노트북의 Zoom 앱인지, 회의실 전용 Zoom Rooms인지 확인하세요. 이름은 비슷하지만 준비할 장비와 운영 조건이 달라집니다.'),
 sec('구성 역할','2. 영상·음성과 조작 장치를 나눕니다','노트북 방식에서는 연결할 카메라·음성 장비가 필요합니다. 전용 룸 방식에서는 실행 장치와 호환 컨트롤러, 계정·라이선스 조건도 확인합니다.',diagram('Zoom 실행 위치','영상·음성','필요 시 컨트롤러')),
 rec('3. 노트북은 MeetUp 2, 전용 룸은 Mini 구성을 검토합니다','소회의실 노트북 연결에는 <strong>MeetUp 2</strong>, Zoom Rooms 어플라이언스 구성에는 <strong>Rally Bar Mini + 호환 Tap IP</strong>를 추천 후보로 잡을 수 있습니다. 현재 플랫폼 지원과 PoE 환경을 함께 확인하세요.','meetup','mini','tapip'),
 sec('운영 확인','4. 실제 회의 시작을 따라 해봅니다','회의 참여, 영상·음성 확인, 자료 공유까지 한 번에 시험하세요. 장비만 정상이어도 계정과 회의 예약 설정이 맞지 않으면 원하는 흐름이 나오지 않을 수 있습니다.',refs('setup','modes','compat'))
],'Zoom 장비 선택은 앱이 실행되는 위치부터 정하면 쉽습니다. 실제 시작 과정을 시험하며 구성과 운영 설정을 함께 맞추세요.')

add('마이크 케이블이 테이블 위를 가로지르거나 이동할 때 걸리나요? 필요한 수음 위치를 정한 뒤 배선을 계획해 보겠습니다.',[
 sec('설치 문제','1. 깔끔함보다 발언 위치가 먼저입니다','케이블을 숨기기 쉬운 곳에만 마이크를 놓으면 필요한 자리의 음성을 놓칠 수 있습니다. 주로 말하는 위치와 통화 결과를 함께 확인하세요.'),
 sec('위치·배선','2. 마이크 위치와 연결 경로를 같이 그립니다','테이블 크기, 케이블 통과 구멍, 사람의 이동 경로를 표시하세요. 제조사 지정 케이블·마운트 조건을 확인하고 임의 연장 계획은 따로 검증합니다.',diagram('발언 위치','마이크 배치','케이블 경로')),
 rec('3. Rally Bar 계열에는 Rally Mic Pod 구성을 검토합니다','호환되는 <strong>Rally Mic Pod</strong>와 공식 설치 옵션을 추천 후보로 검토하세요. 사용할 시스템의 연결 가능 수량과 배치 가이드를 먼저 확인해야 합니다.','mic'),
 sec('설치 후 확인','4. 고정 전에 자리별 통화부터 합니다','자리별 수음과 음소거 조작 접근성을 확인한 뒤 고정 위치를 결정하세요. 배선은 유지보수 시 장치를 확인할 수 있도록 표시해 두는 것이 좋습니다.',refs('mic'))
],'마이크 설치는 수음 위치와 배선 경로를 함께 정하는 작업입니다. 고정 전에 실제 통화로 확인해보세요.')

add('회의실 전체는 보이는데 누가 말하는지는 찾기 어렵나요? 화자 추적이 어떤 화면을 만드는지, 지원 제품과 함께 살펴봅니다.',[
 sec('불편','1. 전체 화면과 발언자 화면은 목적이 다릅니다','전체 참석자를 보는 장면에서는 대화 분위기를 알기 쉽습니다. 반대로 발표자 표정에 집중하려면 발언자가 더 크게 보이는 화면이 필요할 수 있습니다.'),
 sec('기능','2. RightSight 2의 두 모드를 구분합니다','Group View는 참석자 그룹을, Speaker View는 발언자를 중심으로 프레이밍합니다. Speaker View는 필요한 경우 전체 회의실 화면을 작게 함께 보여줍니다.',refs('view')),
 sec('동작 예시','3. 토론과 발표 장면을 비교해 보세요','전체 토론과 한 사람의 발표에서 원하는 화면이 무엇인지 먼저 정하세요. 반향과 화자 위치에 따라 추적 동작이 달라질 수 있습니다.',photo('speaker')),
 rec('4. Rally Bar Mini와 Rally Bar를 추천 후보로 검토합니다','소형~중형 공간은 <strong>Rally Bar Mini</strong>, 중형~대형 공간은 <strong>Rally Bar</strong>부터 검토하세요. 기능 지원뿐 아니라 플랫폼·모드 설정과 실제 좌석의 동작을 확인해야 합니다.','mini','bar')
],'화자 추적은 필요한 화면을 만드는 기능입니다. 우리 회의 장면에서 원하는 모드와 제품을 함께 확인해보세요.')

add('회의 중 목소리가 작거나 주변 소음에 묻히나요? 빔포밍과 소음 억제를 같은 기능으로 보지 않고 역할부터 구분해 보겠습니다.',[
 sec('환경','1. 목소리와 주변 소리가 어떻게 들리는지 봅니다','발언자가 멀어서 작은지, 가까운 키보드나 냉방 소음이 큰지 확인하세요. 음성 불편을 모두 한 가지 원인으로 묶으면 개선 방향을 놓칠 수 있습니다.'),
 sec('기능 의미','2. 빔포밍과 소음 억제는 다른 역할입니다','빔포밍은 여러 마이크의 신호를 조합해 방향에 따른 수음을 조절하는 방식입니다. 노이즈 억제와 에코 처리는 별도 역할이며, 모든 불필요한 소리를 없앤다는 뜻은 아닙니다.',diagram('마이크 신호 조합','방향에 따른 수음','별도 소음·에코 처리')),
 sec('제품 적용','3. 지원 제품에서 실제 음성을 확인합니다','MeetUp 2는 빔포밍 마이크와 소음 억제·에코 처리 기능을 제공합니다. 사양표에 기능이 있어도 실제 공간의 반향과 배치까지 해결됐다고 볼 수는 없습니다.',refs('meetup')+links('meetup')),
 rec('4. 소회의실 영상·음성 구성에는 MeetUp 2를 추천합니다','소회의실에서 영상과 음성을 함께 정리하려면 <strong>MeetUp 2</strong>를 검토하세요. 가까운 자리와 끝자리, 소음이 있는 상황에서 상대방이 듣는 음성을 비교해 보는 것이 좋습니다.','meetup')
],'기능 이름보다 상대방이 실제로 듣는 결과가 중요합니다. 수음·소음 억제·에코 처리의 역할을 나눠 확인해보세요.')

add('카메라 화면을 옮기거나 확대하려면 PTZ가 꼭 필요할까요? 실제 렌즈 움직임과 화면 안의 디지털 조정을 구분해 보겠습니다.',[
 sec('장면','1. 어떤 참석자를 얼마나 크게 보여줄지 정합니다','전체 테이블을 볼지, 멀리 앉은 발표자를 크게 보여줄지 먼저 정하세요. 확대 기능의 이름만으로 원하는 화면을 알기는 어렵습니다.'),
 sec('방식 비교','2. 물리적 움직임과 디지털 조정은 다릅니다','Rally Bar는 모터식 팬·틸트와 광학·디지털 줌을 제공합니다. MeetUp 2는 디지털 팬·틸트·줌을 사용합니다. 같은 화면 이동처럼 보여도 동작 방식과 범위가 다릅니다.',refs('bar','meetup')+diagram('물리적 팬·틸트','디지털 화면 조정')),
 sec('선택 기준','3. 확대 후 화면과 실제 범위를 확인합니다','가장 먼 좌석을 확대했을 때 필요한 얼굴 크기와 화질이 나오는지 확인하세요. 특정 방식이 모든 상황에서 우월하다고 단정하기보다 실제 장면으로 비교합니다.'),
 rec('4. 먼 좌석은 Rally Bar, 소회의실은 MeetUp 2부터 검토합니다','중형 이상 공간의 먼 참석자를 보여줄 목적에는 <strong>Rally Bar</strong>, 소회의실 USB 구성에는 <strong>MeetUp 2</strong>를 추천 후보로 잡으세요. 실제 거리와 필요한 화면에 맞는지 데모로 확인합니다.','bar','meetup')
],'PTZ 선택은 동작 방식보다 필요한 장면에서 시작합니다. 거리·확대 후 화면·운영 조건을 함께 비교하세요.')

add('회의 앱에서 카메라가 목록에 없거나 화면이 검게 나오나요? 장치 미인식과 선택·영상 문제를 구분해 차례로 확인해 보겠습니다.',[
 sec('증상','1. 목록에 없는지, 선택했는데 검은지 구분합니다','카메라 이름이 보이지 않는 경우와 이름은 있지만 영상이 없는 경우를 나눕니다. 제품·OS·앱 버전과 언제 시작된 증상인지 기록하세요.'),
 sec('점검','2. 선택 장치와 연결을 한 번씩 확인합니다','Rally Bar 계열 USB 모드에서는 앱 영상이 노트북 카메라가 아닌 해당 장치를 사용하는지 확인합니다. 장치 자체가 보이지 않으면 전원과 USB 연결, 앱 권한을 제품·OS 공식 안내에 맞춰 점검하세요.',refs('video')+diagram('장치 목록','앱 카메라 선택','영상 확인')),
 rec('3. 장비 보완이 필요할 때 MeetUp 2를 검토합니다','현재 웹캠이 회의실 용도에 맞지 않아 교체를 검토한다면 소회의실에는 <strong>MeetUp 2</strong>를 추천 후보로 잡을 수 있습니다. 권한·케이블·앱 문제는 새 제품에서도 남을 수 있으므로 원인을 먼저 확인하세요.','meetup'),
 sec('정상 확인','4. 실제 회의 앱에서 다시 시험합니다','영상이 나오는지 확인한 뒤 앱을 종료하고 다시 참여해 봅니다. 해결되지 않으면 장치 이름, 연결 경로, 재현 순서를 상담에 전달하세요.',refs('setup'))
],'증상을 나누고 한 단계씩 확인하면 불필요한 교체를 줄일 수 있습니다. 정상 영상 확인과 재접속까지 시험해보세요.')

add('내 목소리만 끊기는지, 상대방 목소리도 끊기는지 헷갈리나요? 연결과 음성 장치를 나눠 원인을 좁혀보겠습니다.',[
 sec('증상','1. 송신과 수신, 특정 상대를 구분합니다','여러 상대와 통화해 어느 방향에서 발생하는지 기록하세요. 음성 끊김만으로 마이크 고장이나 네트워크 문제를 확정할 수는 없습니다.'),
 sec('점검','2. 한 번에 한 조건만 바꿉니다','선택 마이크·스피커를 확인하고, 가능하면 다른 연결 환경과 비교해 보세요. 제품·앱 버전과 발생 시간을 남기면 연결 문제와 장치 문제를 구분하는 데 도움이 됩니다.',diagram('선택 장치','연결 환경 비교','재현 기록')),
 rec('3. 수음 문제가 남을 때만 장비 보완을 검토합니다','끊김이 아니라 특정 자리의 수음 부족으로 확인됐다면 <strong>Rally Bar 계열의 Rally Mic Pod</strong> 확장을 추천 후보로 검토할 수 있습니다. 확장 마이크가 네트워크 지연이나 패킷 손실을 해결하는 것은 아닙니다.','mic'),
 sec('정상 확인','4. 같은 조건에서 재통화하고 기록합니다','자리·앱·통화 상대를 맞춰 결과를 비교하세요. 원인이 불명확하면 네트워크 환경, 선택 장치와 재현 순서를 기술 상담에 전달합니다.',refs('audio','mic'))
],'목소리 끊김과 수음 부족은 구분해야 합니다. 원인에 맞는 조치 후 같은 조건으로 확인하고, 필요한 장비만 보완하세요.')

assert len(drafts)==len(plans)==20
types={'troubleshooting':'문제 해결','room-configuration':'회의실 구성','product-comparison':'제품 비교','product-introduction':'제품 소개','feature-explanation':'기능 설명'}
for draft_index,(plan,draft) in enumerate(zip(plans,drafts)):
 draft.update(id=plan['topic_id'],type=types[plan['template_id']],title=plan['proposed_title'],keyword=plan['keyword'],topic_id=plan['topic_id'],bye='우리 회의실에 맞는 선택에 도움이 되었기를 바랍니다. 환경별 장비 구성과 B2B 견적·데모 상담은 오우션테크놀러지로 문의해 주세요. 감사합니다.')
 assert any(s[3] for s in draft['sections'])
 assert all(s[2].startswith('<p>') for s in draft['sections'])
 # Product awareness is a companion node, separate from the main solution sequence.
 product_keys=[['meetup'],['meetup'],['meetup'],['meetup'],['mic'],['meetup'],['bar'],['tap','tapip'],['mic'],['mini','bar'],['meetup','mini'],['meetup','mini'],['bar','mic'],['meetup','mini'],['mic'],['mini','bar'],['meetup'],['bar','meetup'],['meetup'],['mic']]
 descriptions={
  'meetup':'MeetUp 2는 카메라·마이크·스피커를 통합한 소회의실용 USB 장비입니다. 노트북 BYOD 또는 회의실 PC와 함께 사용하는 제품입니다.',
  'mini':'Rally Bar Mini는 소형~중형 회의실용 올인원 비디오 바입니다. 지원 플랫폼에 맞춰 USB·BYOD·전용 룸 구성을 검토할 수 있습니다.',
  'bar':'Rally Bar는 중형~대형 회의실용 올인원 비디오 바입니다. 카메라와 음성 장비를 통합하고, 지원되는 운영 방식에 맞춰 구성합니다.',
  'mic':'Rally Mic Pod는 호환되는 Rally 시스템의 수음 범위를 보완하는 확장 마이크입니다. 독립 USB 마이크가 아니므로 시스템별 연결 조건을 확인합니다.',
  'tap':'Tap은 호환 회의실 시스템을 조작하는 터치 컨트롤러입니다. 영상·음성 장비를 대신하는 제품이 아닙니다.',
  'tapip':'Tap IP는 네트워크 연결형 터치 컨트롤러입니다. 호환 플랫폼과 PoE 전원 조건을 확인해야 합니다.'}
 keys=product_keys[draft_index]
 recommendation_index=next(i for i,s in enumerate(draft['sections']) if s[3])
 if draft['type']=='문제 해결':
  draft['sections'].pop(recommendation_index)
  attached_to=max(0,recommendation_index-1)
 else:
  attached_to=recommendation_index
 draft['product_notes']=[{'attached_to':attached_to,'role':'product_awareness','label':'관련 제품 알아보기',
  'html':''.join(p('<strong>'+names[k]+'</strong> — '+descriptions[k])+links(k)+refs(k if k in sources else 'compat') for k in keys),
  'purpose':'관련 장비의 이름과 역할을 알리는 보조 설명. 문제 해결의 필수 조치나 구매 권유로 취급하지 않음.'}]
 if draft['type']=='문제 해결':
  draft['closing']={
   'TOPIC-PROP-001':'TV 입력과 화면 연결, 오디오 선택을 나눠 점검하세요. 조치 후 실제 회의 앱에서 영상·소리를 다시 확인하고, 문제가 남으면 연결 정보를 기록해 상담에 전달합니다.',
   'TOPIC-PROP-002':'같은 방의 중복 오디오 접속부터 정리하고 다시 통화해 보세요. 남는 증상과 발생 조건을 기록하면 다음 점검을 구체화할 수 있습니다.',
   'TOPIC-PROP-019':'장치 미인식과 검은 화면을 구분해 연결·선택·권한을 점검하세요. 실제 앱의 정상 영상과 재접속까지 확인하고, 미해결 시 재현 순서를 전달합니다.',
   'TOPIC-PROP-020':'송신·수신 방향과 발생 환경을 구분하고 한 조건씩 비교하세요. 원인을 확정하기 어렵다면 선택 장치·연결 환경·발생 시간을 기록해 기술 상담에 전달합니다.'}[draft['id']]
out=ROOT/'static'
(out/'article-topic-data.js').write_text('window.topicArticleDrafts = '+json.dumps(drafts,ensure_ascii=False,indent=2)+';\n',encoding='utf-8')
archive=ROOT/'content-system/00_system/templates/articles/short-examples'
archive.mkdir(exist_ok=True)
(archive/'articles.json').write_text(json.dumps({'status':'short_editorial_examples','source_checked_at':'2026-10-06','articles':drafts,'sources':sources},ensure_ascii=False,indent=2),encoding='utf-8')
print('Wrote 20 topic-bound short articles with recommendations and source links.')
