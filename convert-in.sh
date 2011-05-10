#! /bin/sh

token="@@SOS_FARMS@@"
script_token='-->'
for f in *.htm
do
    sfile=`tempfile`

    n=`echo $f | sed 's/.htm//'`

    form="form/$n.form"
    html="$n.html"
    if [ -f $form ]; then
        echo "$f <- $form"
        ./formsed.py "$script_token" $f "form/template.txt" $sfile
        ./formsed.py $token $sfile $form $html
    else
        cp $f "$n.html"
    fi

done

chmod 644 *.html


sed -i 's/sed_out_logout_url/{{logout_url}}/g' *.html
sed -i 's/sos_sure_action/{\{sos_sure_action\}}/g' *.html
rm *.htm
