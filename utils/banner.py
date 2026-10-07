# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BhookOuyang <https://github.com/BhookOuyang>

"""Banner asset for AuroraSNodeManager (compressed, decompressed on demand)."""
import base64
import html
import time
import zlib

_BANNER_Z85 = (
    'c-rk++m7R^5`FhqM51{Ck-S?%%7?TxKa!8%)D5b*I8JxYOz(XLX{Hm$hDBXh6~5np_So)!0sbU_-Ua7='
    'BtRE)qOq5OA9C<N1fY+(jMT>7K7>CG(1+Z?tAj4bKMD}gMHC=_$uj7pe2;$$pd)0lK#X}9crnHRf5IOC'
    '=!2k&Ap`^|BNH?p0dM@WzxeHo!h@wFNeUnYKxs#abS->Qh(6%>3c#{t33g628BvJNxex_VV00nmD%RJ+'
    'X&u|^8*`v9pDn%s@LU9-I4@iy4`P5hxtApOMS$M<>b_Yljl@-;!9R!kb_@`Fh;~u5?EFiz`vO4ED|n6}'
    ')ejJ2$kpn~=MZA&(#2Dr2+=wBJ%Ba%C0;g@03&;H^@{R^e1lwC0#VtYJBG*O>k{<7D!17e!87qDM{*Sr'
    '9|QDF3!`#}@e)8s22|iV&*`H^I|3pwG5)Y&3gVOzphI|Jv2_?D!czbp5fdLFyxe2Om#d2+KJ)|%FA<#v'
    'mdIMuWXA&|^K*PSwlnZT3ojV|1YfMy6?=Rb7!hHF+gOC2;e<IpLMS-t>vqEN;Z{YiFoj5-6EP|+Q!s35'
    'ic#*a(b~Hyyon%Hs)NgZ8aB;^$nh<kNQj!0P~#LnG^7X;M37A_eu;0QVz2UOFhtn((ba^vTzxo7It~F<'
    'q!+@F%?Qg{Eg|{2{4CH7K;Zn2^$5Q-@mYiRefX`o3Z_7l2tMzaKj1S!5er0XItt!W)0-!By=K`vEI!wX'
    'kHMks<>=Jhfe;1p6M4jI+k;gJofc*1KO5rnld$O_{cG>g@M2jP2t5Tnaq7Bt#l0{Z*5GacdXiy-Hzlkj'
    'K#AMVql%f7pynh{Gd$54R~<s_35ejM;DZ(3o^mCwG1}k~ssQ|wM{Lnqnha*n{whw>C`N;pYMFVxUiT}&'
    'p#7o!Llufw3&86Yqc+JB1kwCAoTyAUn+?UT9Ys9eIz@_<b-~8f(VlYwmmrye?8q^p62;_PQcw8-_IDSp'
    '2W^DmUfudBKu=1BC7h-1E~;`(Rg@)ffJCDQF9B4nDc>?sc@%u7V1smtLNxgNQ+yR5!fP>)@(0A*FqUkI'
    '$snbrK(TL<|2bbltS^Q{ls57rXf`MCF+jY1lEPJ#cCl8Mlo*QUygx<4!2kha7N=(3Xy!izh;BQfXI?pv'
    'M6(cC$wht6pQA!#Gh)<ZzIp<%cwK)##&B(h7&*v0*$VMze@1|W51+Z;y??DlE@WZE=cq`dopRbDRw9m4'
    '<OfC2i89EM4F=kkN(m>;qog{E&r{h4(aH;{3yqf6M8avr&#9-y7e(&q?JtNB1he({B%`2V>uy1=^<%*&'
    '@uo*;OqcLE2~U_)O6X3Mwa-*QKo*Sqa?}VSwV+BY0g61nhHN*Hp)x-zvbeE{X{Y>+On=VcLx7as2^S~3'
    '34@SbD^Eeg_XqCbvAKx}amTC&d9jEPA9T@#-f=a@0AtXMppK>4Mh&nbG-M}u<hrEZopAAxR7ta7ybpuU'
    '6=98yEqD`JR@G;)08>()Nm&suU@=VC7#+f)t}Ee&OF7goo}1wVK3M0M*g`>X(fV*P_AOr#A~=2m6GLv%'
    'R4SsA$M$v!7AKOTd{q&Ce^(Op!HMX?EC@?&9LA<J-Rz3Qz*h@`E1<KgosC3E0A~~5)_fl_NvN`-<PmD-'
    'bz|3vpx0=f8gVU_B>FVN;34Wr>dt6?+TE}&ggoymzOrr!)QrR-*@#}Z>749CQ3erUR(S<^^*%$_bZRf|'
    'N$k*A0RBaN6A{7|Fv$>`d&Jjj#W;jhM+Jz2)sRlbH^93#S58LRdkvO};~Y`Wjl~j7SoSMoLLFy=FHu=C'
    'mEX=V)HTArGrSIGXW8f^Vp^0g+z}5Fe5l}LOs<2sU+ZF8w?zgC;Z->L0Igo!o6jhKTq63z?yM7hQ-?sI'
    'wV;=p=y>rGz|dvcP1rVAs#b&$O>xxL2kUs*U-axm@c^IlT3mKVa<J=&iA0kkc8(R^)#^8g)&w9MB*q+_'
    'TcvQUa45tmrOmyz8Qo5Kol0l?g*E4hh82v>0P5i$J8%Q&%R^Bb_0AM#ikDG?3GiLlW49h#5b|O%S2JUX'
    'wAKAu<9Sk+X8}SSlxl`3$e6de|HXcLJvYb=LT%TG_8m8Gc5S58%jp|60MG^TVs51xfUTDiYhPjC_cQS7'
    '-4&zH7>EU6b#XZYSMs|zfYe3cyy1n%c`0~&txj47=3ILKPTEQ$sGS>20TXwVXA`tE^q4^V4j?goOl!XJ'
    '9cfcJHg&S|-q0rSD)~n7(*r0tpMjpCPMY+n380G^YlESda@Y?PfD8^=WDvbLGC$WYdO_d{hIQs5AS5kk'
    'Hkw_~<=FG;&Pjam4IzYT)N7!Y2C<x+Q`%4Y1qjHY&vG)9j1ZC8LU0j)sy7!k#=(n`308>g&raGB<?plL'
    'V*Hk(2a>0q<8MUW1?;bSvT%nD3hFjmcy~VmsE!$_hg7>zP_bvhr_yT7&rPryE7pER?V<9~GOO^GE_?X}'
    'z~(3r@?2{pqjPi+QV4Nhq2m;bnOnkhqUaD6Kq;M^zu%7zO}4HiYNQ(N#ff@%4G${gg#}u&1UUqsOkPUn'
    'D#1qAj?Q%aHnw?ug%?G=n$aO^)G|%c(2*8}b_&p`B2=M2HkO4=CHdj*?<;`Z&kD7r&-iTONJvL?x`ihG'
    '-guUYLj*DJ=0zz4m@NlfHF>m?xX@a(M85=|)?$PktvuKE$a$A~^Ik3NLh8!9?4AI0d~Pl!ov$Yec2S^Y'
    '6(9*H?8|ZloP`kiyTNDcB^08YJIiMAc@m$)L*X<@X@LMz^1{W^gssxS7w0=h=v7S~g;i5+41wLqaIito'
    'uSIat?(wCVX>blzf>}ruhMkJ5KM<hSh(7Rgj@y|Sgfg|x3c|Qbb?RLehx#p!lt$jXS04s|JJU|sKG-42'
    'LO15xiHgl)kU86%hSF7sO35!%ozBBx&Usfgkf|c~NM1~FEl^_yLJ9Z-l^Y{M0}%0vE#&%gM|+cR8V5y!'
    '!qb{XDR3Fn7ZuNfj}8!BA~NN=z89aTboi<VCwZj`R18n9QeEX%IrZJ0+B&1tLO?IP_U;M*0?L#*<ebeR'
    ')f}G@Up?^#*}F+H+3*z3l=cRohQ|>(GVf0G0w|wo`7oU1k*kERshb+UdL*9{vYRjiSfc`-efgLsO)`EF'
    'fp<?<=QwhCVo@&leN92z8=y?uUTX+IYsd&Ex!4}U&jF?=Q{`GXI#Qj-7bO5Ly_GNkbXI_ot9k{nEE(w_'
    '<vBp#EJUZ*TsKSpooZ9g)4MRf9)$EGSOJ2ABxKWd&v=D<m{YoCzX#(WS3Wjq%8(4~<s}++ldSrXdbq&='
    'p-b5W7@^bU_yBMYu)CN#PQt-}dfjq4NioD{t1&G`_9jF}z*qk`R4iZ(bc!F=gjFfIZ|LRrPEqaj@R^pE'
    'vtJ#dl`z!_fG8M&WztHZehuLRu+GnIQ1gtK_kC!aWlWYzrpO(g=~K|@9ruQ%OOn0U0?edYJ_=yQP_AHc'
    '0%Fx|t<Fin3?}Bcw>GJwQM^iU1|dj<&u6$d9GwM7TLTRjM7$iPzTh-N3<h9I`?(<$6c|C^h!f1o0V+VH'
    '5G!Ob1AGvllvVKz+BwT$wXV1QHGF8^fmO0!2eW}{sJ{1`7@!voXJ#&S(t<C?9-oonNr1Y!TkJc)Qb}sw'
    '&Ww|0j~ZblfX$Y!(1i#izCE4>$c?mi-WJioA)ZHR|Ktv$YcU{O9aG54b?#7z@eJR22~Jw4J4Swt81<-7'
    'ougwZ+#YjAgqh<3E5+UEM7H9~FWX>4cU8R)%uPX;qseK6D-n8P1w!M19kWed8*`#Y#5sW1nIxq-W4j+p'
    'h*GN8q^Oh(FWhjnPl7KpKDC@O!TYvdF1HUH_~G*E_{uYr=PHKxj14CI_3Lu^_;_4ipY|)yOrEP4-nA>5'
    '|C4uRB*p@~X-(dSpFgyuPks96Rnsu&RnE@3-qnM5r6q>nFY;fzZ;)^M^!W8_xYm6t<MyCwZ+cfW)GEsv'
    'x|L4siY3-0_$mMOyRy%9T9dh82MY0}%GX+8ljnejXSgT~a7|mvnO$|b>wm|)A|1?pRQ>wd<ojsWHq50z'
    '&3--MiCdN6?b)uZ+qLiWPvd=6ytjJwHsZEu%nY~Htdkgs5(H5`P_y(uK3Ok5I!WW;=j0drsm)@p@ojvy'
    '`BhuFL!)PyT|@i4O?LHChIza%`o3vAe%&r#-&M1N%g-O@b@i$2=fAV7cX6fFJhwO6_Lq0{E)SD=-s-X2'
    '6F#!!Nt$2TyKj~$Ti(?(o%(e;-y7KNjE~HD5=YeGIh)~TysOWijXTZedl$Ry`N)`=h4l>29qh{Tt{Jnv'
    'TqZ30+q+uvkwI6VqZYeQvt1e9WkacOrzr#b)~?okq~}SE^~_n$rTNh94DV{(X)@n8b+zUrJx^+^XU1~)'
    '(@oQ%8SgTB;G4(!zN@Q$A5Z$;uKra#N$=`d)Bh%(^bW@KBFUNG`<yPFS>x81S>M^!EABQoiRX0b%o>lO'
    'LAJ>zS8bhjYf15%!-kTP=To}Wt+yg({VLtA9u&535D;z)5;Uhwtx>dWEj5pvHnApjY1U?#(YQHIRpG-$'
    '+*IGdY7L$lWztt?t)+|6%dCmDqDy1b=kqdYU|CvYEPT7rwmxpU9W-n3^pr_8ie?h))Avm83%WFKWzFno'
    'oUug<*w(EhN|R<zN0~I)8K2Yl9qsBFU7Gzey?cy-pRB!Qi)cofRHJC}+@oVXkNWH51YI)g4Mb{v?Q~@S'
    '-IVDq>upbS!SAI^?^*Auu6{RVddqrSb?c9BkfW~=pN{Cf@nmj0S9v~T_Fo}BFP#T`qY_!3dCkaCqc+n%'
    '(esYf?Bv6AO^&)=>w`O8;jhlwI%+dbg|j}<x+7(XkKI+X<Mnym6NYCj@HU|>pMB57NK~iPk@&1TQdWN*'
    ';k#WHI8@*1nBff;IPEq~sZCF%M&h&XNLg+7^Q~}b?>}UClU<FcUvp~HCzg@;oajg$?CS6o?wH|?75?n>'
    'Yf5c~#4-|}ryVIGIo%oHiBq^|4Db6D{(rM?@po6hc~?hVXk<dGyKg_L4|>?;9GTFnd-%h;yW7EO*s29|'
    'o3o#vwyR&KPs|>tT0B3+0$({Xn?3RPSxxKh=rnBJ0($HD+5g(FZs$(S&a`-b#F>aaQ#)({Jx;ZF{$}C7'
    'yZS%h)jyIdO&t'
)

_THRESHOLD = 10
_WINDOW = 10.0

triggered = False
_clicks = []


def banner_text():
    return zlib.decompress(base64.b85decode(_BANNER_Z85)).decode("utf-8")


def register_click():
    """Record one click; return True once THRESHOLD clicks land within WINDOW seconds."""
    global triggered, _clicks
    if triggered:
        return False
    now = time.monotonic()
    _clicks.append(now)
    _clicks = [t for t in _clicks if now - t <= _WINDOW]
    if len(_clicks) >= _THRESHOLD:
        triggered = True
        _clicks = []
        return True
    return False


def reset_session():
    global triggered, _clicks
    triggered = False
    _clicks = []


_VIEWER_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Easter Egg</title>
<style>
  html, body { margin: 0; padding: 0; background: #0b0b0f; color: #d7f0ff; }
  body { text-align: center; }
  pre#art {
    display: inline-block;
    text-align: left;
    font-family: "Consolas", "Menlo", "Monaco", "DejaVu Sans Mono", "Courier New", monospace;
    font-size: 14px;
    line-height: 1.0;
    white-space: pre;
    margin: 0;
    padding: 12px;
    color: #d7f0ff;
    text-shadow: 0 0 2px rgba(120, 200, 255, 0.25);
  }
</style>
</head>
<body>
<pre id="art">__ART__</pre>
<script>
(function () {
  "use strict";
  var pre = document.getElementById("art");
  var base = 14;
  function fit() {
    var avail = document.documentElement.clientWidth - 24;
    var w = pre.scrollWidth;
    var size = base;
    if (w > avail && avail > 0) {
      size = base * avail / w;
    }
    if (size > 40) { size = 40; }
    if (size < 6) { size = 6; }
    pre.style.fontSize = size.toFixed(2) + "px";
  }
  window.addEventListener("load", fit);
  window.addEventListener("resize", fit);
  fit();
})();
</script>
</body>
</html>
"""


def write_viewer(path):
    """Render the banner into a read-only monospace HTML page at ``path``."""
    document = _VIEWER_TEMPLATE.replace("__ART__", html.escape(banner_text()))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(document)
    return path
