export function sheetLayout(count) {
  if(!Number.isInteger(count)||count<1||count>24) throw new RangeError('Expected 1..24 pilot subjects');
  const columns=Math.min(count,3),rows=Math.ceil(count/columns);
  return {width:55+columns*715,height:205+rows*795,
    tiles:Array.from({length:count},(_,i)=>({x:60+(i%columns)*715,y:155+Math.floor(i/columns)*795,size:650}))};
}
