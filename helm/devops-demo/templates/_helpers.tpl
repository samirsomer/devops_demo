{{- define "devops-demo.name" -}}
{{ .Chart.Name }}
{{- end }}

{{- define "devops-demo.fullname" -}}
{{ .Release.Name }}
{{- end }}