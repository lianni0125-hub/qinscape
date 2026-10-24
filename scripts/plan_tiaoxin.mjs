const args=process.argv.slice(2),get=k=>{const i=args.indexOf(k);return i>=0?args[i+1]:''};
const input=get('--prompt')||args.filter(x=>!x.startsWith('--')).join(' ');
if(!input){console.error('Usage: npm run plan:tiaoxin -- --prompt "我最近很悲伤，反复想一件事，希望慢慢稳定"');process.exit(2)}
const has=(...xs)=>xs.some(x=>input.includes(x));
let state='unspecified',direction='和',branch='general_balancing',target='较稳定、可承受的状态';
let arc=['承认当前感受','降低不必要的刺激','建立稳定和可预测性','保留开放而不过度积极的尾声'];
let musical=['中低活动度','清晰但不过强的中心音','适度留白','避免突然明快或强烈高潮'];
let route='tiaoxin';
if(has('悲','难过','伤心','哀','失落')){
  state='sadness';
  if(has('想听悲伤','悲剧美','凄美','写一首悲','体验悲伤')){route='confirm_xieyi_or_tiaoxin';branch='aesthetic_sadness';direction='用户选择';target='确认是表达悲意还是调节状态';arc=['确认创作目的'];musical=['暂不自动改变情绪方向'];}
  else if(has('崩溃','痛哭','受不了','非常强烈','剧烈','喘不过气')){branch='acute_grief';direction='和';arc=['不否定悲伤','降低刺激','建立可预测性','延长呼吸与留白','平稳收束'];musical=['低到中低密度','窄动态','少突变','稳定低音支点','不强迫积极'];}
  else if(has('反复','走不出','停不下来','一直想','沉浸')){branch='repetitive_sorrow';direction='和_then_养';arc=['短暂承接','减少哀伤材料的循环强化','增加承载感','引入微弱生机','稳定收束'];musical=['限制悲性母题复现次数','逐段减少下行回环','增加稳定持续音','尾段轻微拓宽音域'];}
  else if(has('压抑','堵','憋','闷','郁结')){branch='sadness_with_stagnation';direction='泄_then_养';arc=['承认压抑','允许有限表达','疏解郁结','逐渐舒展','温和安顿'];musical=['前段保留张力','设置单一可控峰值','峰后降低密度与跳进','逐渐增加空间和上行势能'];}
  else if(has('哭不出','说不出','无法表达','不敢表达')){branch='unexpressed_grief';direction='泄_then_和';arc=['提供容纳','允许悲意显现','表达与松动','澄清','安顿'];musical=['低音区稀疏开场','中段适度扩大音域','允许一次表达峰值','尾段稳定中心音'];}
  else{branch='sadness_unspecified';direction='和_then_养';arc=['有限承接','澄清与松动','增加支撑','安顿而非强行快乐'];musical=['悲性材料只作起点','避免持续强化商秋清肃意象','逐段提高稳定性','按用户目标决定是否加入舒展或温明'];}
}
const output={mode:'tiaoxin',input,route,assessment:{state,branch,target,diagnostic_claim:false},regulation:{direction,arc,musical},five_tone_usage:{role:'cultural_hypothesis_not_prescription',fixed_sequence:false,next_step:'根据目标选择五音主次与意象，不能由情绪标签直接决定固定调式'},safety:'这是文化性 wellbeing 音乐规划，不是诊断或治疗建议。'};
console.log(JSON.stringify(output,null,2));
