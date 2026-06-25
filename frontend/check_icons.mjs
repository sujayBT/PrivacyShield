import * as l from './node_modules/lucide-react/dist/cjs/lucide-react.js';
const want = ['Table2','Table','FileText','Image','File','MapPin','User','Calendar','Camera','Cpu','Download','CheckCircle','Eye','Upload','Search'];
want.forEach(n => console.log(n, n in l ? 'OK' : 'MISSING'));
